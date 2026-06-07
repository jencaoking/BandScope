"""
.jsc 字节码反编译模块

支持识别和处理多种字节码格式：
- V8 compiled bytecode / snapshot
- QuickJS bytecode
- JerryScript bytecode (CBC)
- 自定义格式
"""

import struct
import os
import subprocess
import tempfile
import json
import re
from pathlib import Path
from enum import Enum
from typing import Optional, List, Dict, Any


class BytecodeType(Enum):
    UNKNOWN = "unknown"
    V8_SNAPSHOT = "v8_snapshot"
    V8_CODE_CACHE = "v8_code_cache"
    QUICKJS = "quickjs"
    JERRYSCRIPT = "jerryscript"
    CUSTOM = "custom"


# JerryScript CBC (Compact Byte Code) 指令定义
# 参考: jerry-core/vm/vm-opcode.h
JERRYSCRIPT_OPCODES = {
    0x00: 'EXT',  # Extended opcode
    0x01: 'NOP',
    0x02: 'ADD',
    0x03: 'SUB',
    0x04: 'MUL',
    0x05: 'DIV',
    0x06: 'MOD',
    0x07: 'EXP',
    0x08: 'BIT_OR',
    0x09: 'BIT_AND',
    0x0A: 'BIT_XOR',
    0x0B: 'SHL',
    0x0C: 'SHR',
    0x0D: 'SHR_U',
    0x0E: 'ADD_I8',
    0x0F: 'ADD_I16',
    0x10: 'SUB_I8',
    0x11: 'SUB_I16',
    0x12: 'MUL_I8',
    0x13: 'MUL_I16',
    0x14: 'NEG',
    0x15: 'NOT',
    0x16: 'BIT_NOT',
    0x17: 'INC',
    0x18: 'DEC',
    0x19: 'INC_I8',
    0x1A: 'INC_I16',
    0x1B: 'DEC_I8',
    0x1C: 'DEC_I16',
    0x1D: 'TYPEOF',
    0x1E: 'INSTANCEOF',
    0x1F: 'IN',
    0x20: 'EQ',
    0x21: 'NE',
    0x22: 'STRICT_EQ',
    0x23: 'STRICT_NE',
    0x24: 'LT',
    0x25: 'GT',
    0x26: 'LE',
    0x27: 'GE',
    0x28: 'LT_NUM',
    0x29: 'GT_NUM',
    0x30: 'LE_NUM',
    0x31: 'GE_NUM',
    0x32: 'TO_NUMBER',
    0x33: 'TO_INT32',
    0x34: 'TO_UINT32',
    0x35: 'TO_BOOLEAN',
    0x36: 'TO_STRING',
    0x37: 'TO_OBJECT',
    0x38: 'TO_PRIMITIVE',
    0x39: 'IS_FINITE',
    0x3A: 'IS_NAN',
    0x3B: 'IS_UNDEFINED',
    0x3C: 'IS_NULL',
    0x3D: 'IS_TRUE',
    0x3E: 'IS_FALSE',
    0x3F: 'IS_OBJECT',
    0x40: 'IS_STRING',
    0x41: 'IS_NUMBER',
    0x42: 'IS_BOOLEAN',
    0x43: 'IS_SYMBOL',
    0x44: 'IS_FUNCTION',
    0x45: 'NEW_OBJECT',
    0x46: 'NEW_ARRAY',
    0x47: 'NEW_REGEXP',
    0x48: 'NEW_DATE',
    0x49: 'NEW_ERROR',
    0x4A: 'NEW_OBJECT_LITERAL',
    0x4B: 'NEW_ARRAY_LITERAL',
    0x4C: 'GET_BY_VAL',
    0x4D: 'GET_BY_IDX',
    0x4E: 'GET_BY_STR_LIT',
    0x4F: 'GET_BY_SYM',
    0x50: 'GET_BY_VAR',
    0x51: 'SET_BY_VAL',
    0x52: 'SET_BY_IDX',
    0x53: 'SET_BY_STR_LIT',
    0x54: 'SET_BY_SYM',
    0x55: 'SET_BY_VAR',
    0x56: 'SET_PROP',
    0x57: 'SET_ELEM',
    0x58: 'DELETE_BY_VAL',
    0x59: 'DELETE_BY_IDX',
    0x5A: 'DELETE_BY_STR_LIT',
    0x5B: 'DELETE_BY_SYM',
    0x5C: 'INCREMENT_BY_VAL',
    0x5D: 'DECREMENT_BY_VAL',
    0x5E: 'INCREMENT_BY_IDX',
    0x5F: 'DECREMENT_BY_IDX',
    0x60: 'INCREMENT_BY_STR_LIT',
    0x61: 'DECREMENT_BY_STR_LIT',
    0x62: 'INCREMENT_BY_SYM',
    0x63: 'DECREMENT_BY_SYM',
    0x64: 'CALL',
    0x65: 'CALL_EVAL',
    0x66: 'CALL_CONSTRUCTOR',
    0x67: 'CALL_IMMEDIATE',
    0x68: 'CALL_IMMEDIATE_0',
    0x69: 'CALL_IMMEDIATE_1',
    0x6A: 'CALL_IMMEDIATE_2',
    0x6B: 'CALL_IMMEDIATE_3',
    0x6C: 'CALL_IMMEDIATE_4',
    0x6D: 'CALL_ARG_0',
    0x6E: 'CALL_ARG_1',
    0x6F: 'CALL_ARG_2',
    0x70: 'RETURN',
    0x71: 'RETURN_UNDEFINED',
    0x72: 'RETURN_FALSE',
    0x73: 'RETURN_TRUE',
    0x74: 'RETURN_NULL',
    0x75: 'THROW',
    0x76: 'THROW_LIT',
    0x77: 'JMP',
    0x78: 'JMP_TRUE',
    0x79: 'JMP_FALSE',
    0x7A: 'JMP_UNDEFINED',
    0x7B: 'JMP_NULL',
    0x7C: 'JMP_NON_NULL',
    0x7D: 'JMP_NON_UNDEFINED',
    0x7E: 'JMP_REGEXP',
    0x7F: 'JMP_IN',
    0x80: 'JMP_INSTANCEOF',
    0x81: 'JMP_TYPEOF',
    0x82: 'JMP_DELETE_TRUE',
    0x83: 'JMP_DELETE_FALSE',
    0x84: 'JMP_NEG',
    0x85: 'JMP_ZERO',
    0x86: 'JMP_NON_ZERO',
    0x87: 'JMP_EQ',
    0x88: 'JMP_NE',
    0x89: 'JMP_STRICT_EQ',
    0x8A: 'JMP_STRICT_NE',
    0x8B: 'JMP_LT',
    0x8C: 'JMP_GT',
    0x8D: 'JMP_LE',
    0x8E: 'JMP_GE',
    0x8F: 'JMP_LT_NUM',
    0x90: 'JMP_GT_NUM',
    0x91: 'JMP_LE_NUM',
    0x92: 'JMP_GE_NUM',
    0x93: 'JMP_ADD',
    0x94: 'JMP_SUB',
    0x95: 'JMP_MUL',
    0x96: 'JMP_DIV',
    0x97: 'JMP_MOD',
    0x98: 'JMP_BIT_OR',
    0x99: 'JMP_BIT_AND',
    0x9A: 'JMP_BIT_XOR',
    0x9B: 'JMP_SHL',
    0x9C: 'JMP_SHR',
    0x9D: 'JMP_SHR_U',
    0x9E: 'JMP_INC',
    0x9F: 'JMP_DEC',
    0xA0: 'PUSH_UNDEFINED',
    0xA1: 'PUSH_NULL',
    0xA2: 'PUSH_TRUE',
    0xA3: 'PUSH_FALSE',
    0xA4: 'PUSH_UNDEFINED_N',
    0xA5: 'PUSH_NULL_N',
    0xA6: 'PUSH_TRUE_N',
    0xA7: 'PUSH_FALSE_N',
    0xA8: 'PUSH_UNDEFINED_2',
    0xA9: 'PUSH_NULL_2',
    0xAA: 'PUSH_TRUE_2',
    0xAB: 'PUSH_FALSE_2',
    0xAC: 'PUSH_UNDEFINED_3',
    0xAD: 'PUSH_NULL_3',
    0xAE: 'PUSH_TRUE_3',
    0xAF: 'PUSH_FALSE_3',
    0xB0: 'PUSH_LIT',
    0xB1: 'PUSH_LIT_BYTE',
    0xB2: 'PUSH_CURR_CONTEXT',
    0xB3: 'PUSH_ARG',
    0xB4: 'PUSH_LOCAL',
    0xB5: 'PUSH_LOCAL_BYTE',
    0xB6: 'PUSH_LOCAL_I8',
    0xB7: 'PUSH_LOCAL_I16',
    0xB8: 'PUSH_GLOBAL',
    0xB9: 'PUSH_GLOBAL_BYTE',
    0xBA: 'PUSH_GLOBAL_I8',
    0xBB: 'PUSH_GLOBAL_I16',
    0xBC: 'PUSH_THIS',
    0xBD: 'PUSH_HOLE',
    0xBE: 'PUSH_ARG_COUNT',
    0xBF: 'PUSH_UNDEFINED_ARG',
    0xC0: 'STORE_LOCAL',
    0xC1: 'STORE_LOCAL_BYTE',
    0xC2: 'STORE_LOCAL_I8',
    0xC3: 'STORE_LOCAL_I16',
    0xC4: 'STORE_GLOBAL',
    0xC5: 'STORE_GLOBAL_BYTE',
    0xC6: 'STORE_GLOBAL_I8',
    0xC7: 'STORE_GLOBAL_I16',
    0xC8: 'STORE_ARG',
    0xC9: 'STORE_ARG_BYTE',
    0xCA: 'STORE_ARG_I8',
    0xCB: 'STORE_ARG_I16',
    0xCC: 'STORE_THIS',
    0xCD: 'POP',
    0xCE: 'POP_N',
    0xCF: 'POP_2',
    0xD0: 'POP_3',
    0xD1: 'POP_N_2',
    0xD2: 'POP_N_3',
    0xD3: 'DUP',
    0xD4: 'DUP_2',
    0xD5: 'DUP_3',
    0xD6: 'SWAP',
    0xD7: 'SWAP_2',
    0xD8: 'SWAP_3',
    0xD9: 'ROT',
    0xDA: 'ROT_2',
    0xDB: 'ROT_3',
    0xDC: 'COPY_TO_LOCAL',
    0xDD: 'COPY_FROM_LOCAL',
    0xDE: 'COPY_TO_LOCAL_BYTE',
    0xDF: 'COPY_FROM_LOCAL_BYTE',
    0xE0: 'COPY_TO_LOCAL_I8',
    0xE1: 'COPY_FROM_LOCAL_I8',
    0xE2: 'COPY_TO_LOCAL_I16',
    0xE3: 'COPY_FROM_LOCAL_I16',
    0xE4: 'COPY_TO_ARG',
    0xE5: 'COPY_FROM_ARG',
    0xE6: 'COPY_TO_ARG_BYTE',
    0xE7: 'COPY_FROM_ARG_BYTE',
    0xE8: 'COPY_TO_ARG_I8',
    0xE9: 'COPY_FROM_ARG_I8',
    0xEA: 'COPY_TO_ARG_I16',
    0xEB: 'COPY_FROM_ARG_I16',
    0xEC: 'COPY_TO_GLOBAL',
    0xED: 'COPY_FROM_GLOBAL',
    0xEE: 'COPY_TO_GLOBAL_BYTE',
    0xEF: 'COPY_FROM_GLOBAL_BYTE',
    0xF0: 'COPY_TO_GLOBAL_I8',
    0xF1: 'COPY_FROM_GLOBAL_I8',
    0xF2: 'COPY_TO_GLOBAL_I16',
    0xF3: 'COPY_FROM_GLOBAL_I16',
    0xF4: 'COPY_TO_THIS',
    0xF5: 'COPY_FROM_THIS',
    0xF6: 'DEFERRED',
    0xF7: 'DEFERRED_BRANCH',
    0xF8: 'DEFERRED_CALL',
    0xF9: 'DEFERRED_CALL_0',
    0xFA: 'DEFERRED_CALL_1',
    0xFB: 'DEFERRED_CALL_2',
    0xFC: 'DEFERRED_CALL_3',
    0xFD: 'DEFERRED_CALL_4',
    0xFE: 'DEFERRED_CONSTRUCTOR',
    0xFF: 'DEFERRED_EVAL',
}

# JerryScript 扩展指令 (EXT opcode)
JERRYSCRIPT_EXT_OPCODES = {
    0x00: 'EXT_DEBUGGER',
    0x01: 'EXT_WITH_CREATE_CONTEXT',
    0x02: 'EXT_WITH_DELETE_CONTEXT',
    0x03: 'EXT_CATCH_CREATE_CONTEXT',
    0x04: 'EXT_CATCH_DELETE_CONTEXT',
    0x05: 'EXT_CLOSE',
    0x06: 'EXT_NEW_FUNCTION',
    0x07: 'EXT_GET_BY_INDEX_SHORT',
    0x08: 'EXT_SET_BY_INDEX_SHORT',
    0x09: 'EXT_DELETE_BY_INDEX_SHORT',
    0x0A: 'EXT_INCREMENT_BY_INDEX_SHORT',
    0x0B: 'EXT_DECREMENT_BY_INDEX_SHORT',
    0x0C: 'EXT_JMP_BYTE',
    0x0D: 'EXT_JMP_TRUE_BYTE',
    0x0E: 'EXT_JMP_FALSE_BYTE',
    0x0F: 'EXT_JMP_UNDEFINED_BYTE',
    0x10: 'EXT_JMP_NULL_BYTE',
    0x11: 'EXT_JMP_NON_NULL_BYTE',
    0x12: 'EXT_JMP_NON_UNDEFINED_BYTE',
    0x13: 'EXT_JMP_REGEXP_BYTE',
    0x14: 'EXT_JMP_IN_BYTE',
    0x15: 'EXT_JMP_INSTANCEOF_BYTE',
    0x16: 'EXT_JMP_TYPEOF_BYTE',
    0x17: 'EXT_JMP_DELETE_TRUE_BYTE',
    0x18: 'EXT_JMP_DELETE_FALSE_BYTE',
    0x19: 'EXT_JMP_NEG_BYTE',
    0x20: 'EXT_JMP_ZERO_BYTE',
    0x21: 'EXT_JMP_NON_ZERO_BYTE',
    0x22: 'EXT_JMP_EQ_BYTE',
    0x23: 'EXT_JMP_NE_BYTE',
    0x24: 'EXT_JMP_STRICT_EQ_BYTE',
    0x25: 'EXT_JMP_STRICT_NE_BYTE',
    0x26: 'EXT_JMP_LT_BYTE',
    0x27: 'EXT_JMP_GT_BYTE',
    0x28: 'EXT_JMP_LE_BYTE',
    0x29: 'EXT_JMP_GE_BYTE',
    0x30: 'EXT_JMP_LT_NUM_BYTE',
    0x31: 'EXT_JMP_GT_NUM_BYTE',
    0x32: 'EXT_JMP_LE_NUM_BYTE',
    0x33: 'EXT_JMP_GE_NUM_BYTE',
    0x34: 'EXT_PUSH_INT8',
    0x35: 'EXT_PUSH_INT16',
    0x36: 'EXT_PUSH_INT32',
    0x37: 'EXT_PUSH_DOUBLE',
    0x38: 'EXT_PUSH_FLOAT32',
    0x39: 'EXT_ADD_INT8',
    0x3A: 'EXT_ADD_INT16',
    0x3B: 'EXT_SUB_INT8',
    0x3C: 'EXT_SUB_INT16',
    0x3D: 'EXT_MUL_INT8',
    0x3E: 'EXT_MUL_INT16',
    0x3F: 'EXT_INC_INT8',
    0x40: 'EXT_INC_INT16',
    0x41: 'EXT_DEC_INT8',
    0x42: 'EXT_DEC_INT16',
    0x43: 'EXT_PUSH_CONTEXT',
    0x44: 'EXT_PUSH_ARG_N',
    0x45: 'EXT_STORE_ARG_N',
    0x46: 'EXT_COPY_TO_ARG_N',
    0x47: 'EXT_COPY_FROM_ARG_N',
    0x48: 'EXT_CALL_ARG_N',
    0x49: 'EXT_CALL_IMMEDIATE_ARG_N',
    0x4A: 'EXT_GET_BY_STR_LIT_SHORT',
    0x4B: 'EXT_SET_BY_STR_LIT_SHORT',
    0x4C: 'EXT_DELETE_BY_STR_LIT_SHORT',
    0x4D: 'EXT_INCREMENT_BY_STR_LIT_SHORT',
    0x4E: 'EXT_DECREMENT_BY_STR_LIT_SHORT',
    0x4F: 'EXT_GET_BY_SYM_SHORT',
    0x50: 'EXT_SET_BY_SYM_SHORT',
    0x51: 'EXT_DELETE_BY_SYM_SHORT',
    0x52: 'EXT_INCREMENT_BY_SYM_SHORT',
    0x53: 'EXT_DECREMENT_BY_SYM_SHORT',
    0x54: 'EXT_GET_BY_STR_LIT_BYTE',
    0x55: 'EXT_SET_BY_STR_LIT_BYTE',
    0x56: 'EXT_DELETE_BY_STR_LIT_BYTE',
    0x57: 'EXT_INCREMENT_BY_STR_LIT_BYTE',
    0x58: 'EXT_DECREMENT_BY_STR_LIT_BYTE',
    0x59: 'EXT_GET_BY_SYM_BYTE',
    0x5A: 'EXT_SET_BY_SYM_BYTE',
    0x5B: 'EXT_DELETE_BY_SYM_BYTE',
    0x5C: 'EXT_INCREMENT_BY_SYM_BYTE',
    0x5D: 'EXT_DECREMENT_BY_SYM_BYTE',
    0x5E: 'EXT_FOR_IN',
    0x5F: 'EXT_FOR_OF',
    0x60: 'EXT_FOR_OF_NEXT',
    0x61: 'EXT_WHILE',
    0x62: 'EXT_WHILE_NEXT',
    0x63: 'EXT_DO_WHILE',
    0x64: 'EXT_FOR',
    0x65: 'EXT_FOR_NEXT',
    0x66: 'EXT_IF',
    0x67: 'EXT_IF_ELSE',
    0x68: 'EXT_TRY_FINALLY',
    0x69: 'EXT_TRY_CATCH',
    0x6A: 'EXT_TRY_CATCH_FINALLY',
    0x6B: 'EXT_WITH',
    0x6C: 'EXT_SWITCH',
    0x6D: 'EXT_DEBUGGER_STATEMENT',
    0x6E: 'EXT_PUSH_BUILTIN',
    0x6F: 'EXT_NEW_BUILTIN',
    0x70: 'EXT_NEW_BUILTIN_ARG_0',
    0x71: 'EXT_NEW_BUILTIN_ARG_1',
    0x72: 'EXT_NEW_BUILTIN_ARG_2',
    0x73: 'EXT_NEW_BUILTIN_ARG_3',
    0x74: 'EXT_NEW_BUILTIN_ARG_4',
    0x75: 'EXT_CALL_BUILTIN',
    0x76: 'EXT_CALL_BUILTIN_0',
    0x77: 'EXT_CALL_BUILTIN_1',
    0x78: 'EXT_CALL_BUILTIN_2',
    0x79: 'EXT_CALL_BUILTIN_3',
    0x7A: 'EXT_CALL_BUILTIN_4',
    0x7B: 'EXT_CALL_BUILTIN_ARG_N',
    0x7C: 'EXT_GET_BUILTIN_PROPERTY',
    0x7D: 'EXT_SET_BUILTIN_PROPERTY',
    0x7E: 'EXT_DELETE_BUILTIN_PROPERTY',
    0x7F: 'EXT_INCREMENT_BUILTIN_PROPERTY',
    0x80: 'EXT_DECREMENT_BUILTIN_PROPERTY',
    0x81: 'EXT_GET_REGEXP_PROPERTY',
    0x82: 'EXT_SET_REGEXP_PROPERTY',
    0x83: 'EXT_DELETE_REGEXP_PROPERTY',
    0x84: 'EXT_INCREMENT_REGEXP_PROPERTY',
    0x85: 'EXT_DECREMENT_REGEXP_PROPERTY',
    0x86: 'EXT_JMP_TABLE',
    0x87: 'EXT_JMP_TABLE_BYTE',
    0x88: 'EXT_PUSH_REGEXP_RESULT',
    0x89: 'EXT_PUSH_REGEXP_RESULT_INDEX',
    0x8A: 'EXT_PUSH_REGEXP_RESULT_INDEX_BYTE',
    0x8B: 'EXT_PUSH_REGEXP_RESULT_VALUE',
    0x8C: 'EXT_PUSH_REGEXP_RESULT_VALUE_BYTE',
    0x8D: 'EXT_REGEXP_EXEC',
    0x8E: 'EXT_REGEXP_TEST',
    0x8F: 'EXT_REGEXP_MATCH',
    0x90: 'EXT_REGEXP_SEARCH',
    0x91: 'EXT_REGEXP_REPLACE',
    0x92: 'EXT_REGEXP_SPLIT',
    0x93: 'EXT_STRING_INDEXOF',
    0x94: 'EXT_STRING_LASTINDEXOF',
    0x95: 'EXT_STRING_CHARAT',
    0x96: 'EXT_STRING_CHARCODEAT',
    0x97: 'EXT_STRING_CONCAT',
    0x98: 'EXT_STRING_SLICE',
    0x99: 'EXT_STRING_SUBSTRING',
    0x9A: 'EXT_STRING_SUBSTR',
    0x9B: 'EXT_STRING_TOLOWERCASE',
    0x9C: 'EXT_STRING_TOUPPERCASE',
    0x9D: 'EXT_STRING_TRIM',
    0x9E: 'EXT_STRING_TRIMSTART',
    0x9F: 'EXT_STRING_TRIMEND',
    0xA0: 'EXT_STRING_STARTSWITH',
    0xA1: 'EXT_STRING_ENDSWITH',
    0xA2: 'EXT_STRING_INCLUDES',
    0xA3: 'EXT_STRING_REPEAT',
    0xA4: 'EXT_STRING_PADSTART',
    0xA5: 'EXT_STRING_PADEND',
    0xA6: 'EXT_ARRAY_PUSH',
    0xA7: 'EXT_ARRAY_POP',
    0xA8: 'EXT_ARRAY_SHIFT',
    0xA9: 'EXT_ARRAY_UNSHIFT',
    0xAA: 'EXT_ARRAY_SPLICE',
    0xAB: 'EXT_ARRAY_SLICE',
    0xAC: 'EXT_ARRAY_CONCAT',
    0xAD: 'EXT_ARRAY_JOIN',
    0xAE: 'EXT_ARRAY_INDEXOF',
    0xAF: 'EXT_ARRAY_LASTINDEXOF',
    0xB0: 'EXT_ARRAY_INCLUDES',
    0xB1: 'EXT_ARRAY_REVERSE',
    0xB2: 'EXT_ARRAY_SORT',
    0xB3: 'EXT_ARRAY_MAP',
    0xB4: 'EXT_ARRAY_FILTER',
    0xB5: 'EXT_ARRAY_REDUCE',
    0xB6: 'EXT_ARRAY_REDUCE_RIGHT',
    0xB7: 'EXT_ARRAY_FOR_EACH',
    0xB8: 'EXT_ARRAY_EVERY',
    0xB9: 'EXT_ARRAY_SOME',
    0xBA: 'EXT_ARRAY_FIND',
    0xBB: 'EXT_ARRAY_FIND_INDEX',
    0xBC: 'EXT_ARRAY_FILL',
    0xBD: 'EXT_ARRAY_COPY_WITHIN',
    0xBE: 'EXT_DATE_GET_FULL_YEAR',
    0xBF: 'EXT_DATE_GET_MONTH',
    0xC0: 'EXT_DATE_GET_DATE',
    0xC1: 'EXT_DATE_GET_DAY',
    0xC2: 'EXT_DATE_GET_HOURS',
    0xC3: 'EXT_DATE_GET_MINUTES',
    0xC4: 'EXT_DATE_GET_SECONDS',
    0xC5: 'EXT_DATE_GET_MILLISECONDS',
    0xC6: 'EXT_DATE_GET_TIME',
    0xC7: 'EXT_DATE_GET_TIMEZONE_OFFSET',
    0xC8: 'EXT_DATE_GET_UTC_FULL_YEAR',
    0xC9: 'EXT_DATE_GET_UTC_MONTH',
    0xCA: 'EXT_DATE_GET_UTC_DATE',
    0xCB: 'EXT_DATE_GET_UTC_DAY',
    0xCC: 'EXT_DATE_GET_UTC_HOURS',
    0xCD: 'EXT_DATE_GET_UTC_MINUTES',
    0xCE: 'EXT_DATE_GET_UTC_SECONDS',
    0xCF: 'EXT_DATE_GET_UTC_MILLISECONDS',
    0xD0: 'EXT_DATE_SET_FULL_YEAR',
    0xD1: 'EXT_DATE_SET_MONTH',
    0xD2: 'EXT_DATE_SET_DATE',
    0xD3: 'EXT_DATE_SET_HOURS',
    0xD4: 'EXT_DATE_SET_MINUTES',
    0xD5: 'EXT_DATE_SET_SECONDS',
    0xD6: 'EXT_DATE_SET_MILLISECONDS',
    0xD7: 'EXT_DATE_SET_TIME',
    0xD8: 'EXT_DATE_SET_UTC_FULL_YEAR',
    0xD9: 'EXT_DATE_SET_UTC_MONTH',
    0xDA: 'EXT_DATE_SET_UTC_DATE',
    0xDB: 'EXT_DATE_SET_UTC_HOURS',
    0xDC: 'EXT_DATE_SET_UTC_MINUTES',
    0xDD: 'EXT_DATE_SET_UTC_SECONDS',
    0xDE: 'EXT_DATE_SET_UTC_MILLISECONDS',
    0xDF: 'EXT_DATE_TO_STRING',
    0xE0: 'EXT_DATE_TO_LOCALE_STRING',
    0xE1: 'EXT_DATE_TO_GMT_STRING',
    0xE2: 'EXT_DATE_TO_ISO_STRING',
    0xE3: 'EXT_DATE_GET_TIME',
    0xE4: 'EXT_OBJECT_ASSIGN',
    0xE5: 'EXT_OBJECT_CREATE',
    0xE6: 'EXT_OBJECT_DEFINE_PROPERTY',
    0xE7: 'EXT_OBJECT_DELETE_PROPERTY',
    0xE8: 'EXT_OBJECT_FREEZE',
    0xE9: 'EXT_OBJECT_GET_OWN_PROPERTY_DESCRIPTOR',
    0xEA: 'EXT_OBJECT_GET_PROTOTYPE_OF',
    0xEB: 'EXT_OBJECT_HAS_OWN_PROPERTY',
    0xEC: 'EXT_OBJECT_IS_FROZEN',
    0xED: 'EXT_OBJECT_IS_SEALED',
    0xEE: 'EXT_OBJECT_PREVENT_EXTENSIONS',
    0xEF: 'EXT_OBJECT_SEAL',
    0xF0: 'EXT_OBJECT_TO_STRING',
    0xF1: 'EXT_FUNCTION_TO_STRING',
    0xF2: 'EXT_ERROR_TO_STRING',
    0xF3: 'EXT_NUMBER_TO_STRING',
    0xF4: 'EXT_BOOLEAN_TO_STRING',
    0xF5: 'EXT_SYMBOL_TO_STRING',
    0xF6: 'EXT_JSON_STRINGIFY',
    0xF7: 'EXT_JSON_PARSE',
    0xF8: 'EXT_PARSE_FLOAT',
    0xF9: 'EXT_PARSE_INT',
    0xFA: 'EXT_IS_ARRAY',
    0xFB: 'EXT_IS_FINITE',
    0xFC: 'EXT_IS_NAN',
    0xFD: 'EXT_DECODE_URI',
    0xFE: 'EXT_DECODE_URI_COMPONENT',
    0xFF: 'EXT_ENCODE_URI',
}


class JSCDecompiler:
    """JSC 字节码反编译器"""

    # 已知的字节码魔数
    MAGIC_NUMBERS = {
        b'\xc0\xde\x01\x00': BytecodeType.V8_SNAPSHOT,
        b'\xc0\xde': BytecodeType.V8_CODE_CACHE,
        b'qjs\x00': BytecodeType.QUICKJS,
        b'JS\x00\x00': BytecodeType.JERRYSCRIPT,
    }

    def __init__(self, node_path: str = "node"):
        self.node_path = node_path

    def detect_type(self, filepath: str) -> BytecodeType:
        """检测 .jsc 文件的字节码类型"""
        with open(filepath, 'rb') as f:
            header = f.read(16)

        for magic, btype in self.MAGIC_NUMBERS.items():
            if header.startswith(magic):
                return btype

        # 进一步分析头部特征
        if self._check_v8_features(header):
            return BytecodeType.V8_SNAPSHOT
        if self._check_quickjs_features(filepath):
            return BytecodeType.QUICKJS

        return BytecodeType.UNKNOWN

    def _check_v8_features(self, header: bytes) -> bool:
        """检查是否为 V8 格式"""
        # V8 字节码通常在头部包含版本号
        if len(header) >= 8:
            # 检查是否包含合理的 V8 版本号
            version = struct.unpack('<I', header[4:8])[0]
            if 10000 < version < 20000:  # V8 版本号范围
                return True
        return False

    def _check_quickjs_features(self, filepath: str) -> bool:
        """检查是否为 QuickJS 格式"""
        try:
            size = os.path.getsize(filepath)
            # QuickJS 字节码有特定的大小和结构特征
            with open(filepath, 'rb') as f:
                header = f.read(4)
                # QuickJS 字节码标记
                if header == b'qjs\x00':
                    return True
                # 某些变体的标记
                if header[:3] == b'qjs':
                    return True
        except Exception:
            pass
        return False

    def decompile(self, filepath: str) -> Optional[str]:
        """反编译 .jsc 文件"""
        btype = self.detect_type(filepath)

        print(f"  检测到字节码类型: {btype.value}")

        decompile_methods = {
            BytecodeType.V8_SNAPSHOT: self._decompile_v8_snapshot,
            BytecodeType.V8_CODE_CACHE: self._decompile_v8_cache,
            BytecodeType.QUICKJS: self._decompile_quickjs,
            BytecodeType.JERRYSCRIPT: self._decompile_jerryscript,
            BytecodeType.UNKNOWN: self._decompile_generic,
        }

        method = decompile_methods.get(btype,
                                        self._decompile_generic)
        return method(filepath)

    def _decompile_v8_snapshot(self,
                                filepath: str) -> Optional[str]:
        """反编译 V8 snapshot 字节码"""
        script = f"""
const v8 = require('v8');
const vm = require('vm');
const fs = require('fs');

try {{
    const bytecode = fs.readFileSync('{filepath.replace("\\", "\\\\")}');

    // 方法1: 尝试作为 cached data
    const script = new vm.Script('', {{ cachedData: bytecode }});
    if (script.cachedDataRejected === false) {{
        console.log(script.toString());
        process.exit(0);
    }}
}} catch(e) {{
    // 方法2: 尝试反序列化
    try {{
        const ctx = v8.deserialize(
            fs.readFileSync('{filepath.replace("\\", "\\\\")}')
        );
        console.log(JSON.stringify(ctx, null, 2));
    }} catch(e2) {{
        console.error('V8反编译失败: ' + e2.message);
        process.exit(1);
    }}
}}
"""
        return self._run_node_script(script)

    def _decompile_v8_cache(self,
                             filepath: str) -> Optional[str]:
        """反编译 V8 code cache"""
        # V8 code cache 通常需要特殊处理
        return self._decompile_v8_snapshot(filepath)

    def _decompile_quickjs(self,
                            filepath: str) -> Optional[str]:
        """
        反编译 QuickJS 字节码
        QuickJS 有开源的字节码格式，可以手动解析
        """
        try:
            return self._parse_quickjs_bytecode(filepath)
        except Exception as e:
            print(f"  QuickJS 解析失败: {e}")
            return self._try_external_tool(
                'quickjs-decompiler', filepath
            )

    def _parse_quickjs_bytecode(self,
                                  filepath: str) -> Optional[str]:
        """
        手动解析 QuickJS 字节码
        QuickJS 字节码格式是公开的，可以精确解析
        """
        with open(filepath, 'rb') as f:
            data = f.read()

        # QuickJS 字节码结构
        # 参考: quickjs/quickjs.c 中的 bc_read_* 函数

        pos = 0
        result_parts = []

        # 读取头部标记
        tag = data[pos:pos+4]
        pos += 4

        if tag != b'qjs\x00':
            # 可能是变体格式
            return None

        # 读取版本
        version = struct.unpack('>I', data[pos:pos+4])[0]
        pos += 4

        result_parts.append(
            f"// QuickJS Bytecode v{version}"
        )
        result_parts.append(
            f"// 文件大小: {len(data)} bytes"
        )
        result_parts.append("")

        # 解析字节码中的常量池和指令
        # 这里是简化的解析，完整的需要参考 quickjs 源码
        try:
            functions = self._parse_qjs_functions(data, pos)
            for func in functions:
                result_parts.append(
                    f"// Function: {func['name']}"
                )
                result_parts.append(
                    f"//   locals: {func['locals']}"
                )
                result_parts.append(
                    f"//   bytecode length: "
                    f"{func['bytecode_len']}"
                )
                result_parts.append("")
        except Exception:
            result_parts.append(
                "// [无法完整解析字节码指令]"
            )

        return '\n'.join(result_parts)

    def _parse_qjs_functions(self, data: bytes,
                              start: int) -> list:
        """解析 QuickJS 字节码中的函数定义"""
        functions = []
        pos = start

        try:
            while pos < len(data) - 4:
                # 读取标签
                tag = data[pos]
                pos += 1

                if tag == 0:  # end of bytecode
                    break

                # 简化的函数头解析
                if pos + 8 > len(data):
                    break

                # 读取函数名长度
                name_len = struct.unpack(
                    '<H', data[pos:pos+2]
                )[0]
                pos += 2

                if name_len > 0 and pos + name_len <= len(data):
                    name = data[pos:pos+name_len].decode(
                        'utf-8', errors='replace'
                    )
                    pos += name_len
                else:
                    name = '<anonymous>'

                # 跳过函数体（简化处理）
                locals_count = struct.unpack(
                    '<I', data[pos:pos+4]
                )[0] if pos + 4 <= len(data) else 0
                pos += 4

                bytecode_len = struct.unpack(
                    '<I', data[pos:pos+4]
                )[0] if pos + 4 <= len(data) else 0
                pos += 4

                functions.append({
                    'name': name,
                    'locals': locals_count,
                    'bytecode_len': bytecode_len,
                })

                # 跳过字节码体
                pos += bytecode_len

        except (struct.error, IndexError):
            pass

        return functions

    def _decompile_jerryscript(self,
                                filepath: str) -> Optional[str]:
        """反编译 JerryScript CBC 字节码"""
        try:
            with open(filepath, 'rb') as f:
                data = f.read()

            result = []
            result.append(
                f"// JerryScript CBC Bytecode"
            )
            result.append(
                f"// 文件大小: {len(data)} bytes"
            )
            result.append("")

            # 解析 JerryScript CBC 字节码结构
            parsed = self._parse_jerryscript_bytecode(data)
            
            if parsed:
                # 输出字面量池
                if parsed['literals']:
                    result.append("// === 字面量池 ===")
                    for i, lit in enumerate(parsed['literals']):
                        result.append(f"// [{i}] {repr(lit)}")
                    result.append("")
                
                # 输出函数定义
                if parsed['functions']:
                    result.append("// === 函数定义 ===")
                    for func in parsed['functions']:
                        result.append(f"function {func['name']}(")
                        if func['params']:
                            result.append(f"  {', '.join(func['params'])}")
                        result.append(f") {{")
                        result.append(f"  // locals: {func['locals']}")
                        result.append(f"  // scope depth: {func['scope_depth']}")
                        if func['bytecode']:
                            result.append("  // 字节码指令:")
                            for instr in func['bytecode'][:50]:  # 限制输出数量
                                result.append(f"  //   {instr}")
                            if len(func['bytecode']) > 50:
                                result.append(f"  //   ... (还有 {len(func['bytecode']) - 50} 条指令)")
                        result.append("}")
                        result.append("")
                
                # 输出还原的JavaScript代码
                if parsed['code']:
                    result.append("// === 还原的 JavaScript 代码 ===")
                    result.append("")
                    result.extend(parsed['code'])
            
            # 如果没有成功解析，回退到字符串提取
            if not result or len(result) <= 3:
                strings = self._extract_strings(data)
                if strings:
                    result.append("// 提取的字符串字面量:")
                for s in strings:
                    if len(s) > 2:
                        result.append(f'// "{s}"')

            return '\n'.join(result)

        except Exception as e:
            return f"// JerryScript 解析失败: {e}"

    def _parse_jerryscript_bytecode(self, data: bytes) -> dict:
        """解析 JerryScript CBC 字节码结构"""
        result = {
            'literals': [],
            'functions': [],
            'code': []
        }
        
        if len(data) < 8:
            return result
        
        pos = 0
        
        # 检查标准 JerryScript 魔数
        if data[pos:pos+4] == b'JS\x00\x00':
            pos += 4
            # 读取版本号
            version = struct.unpack('<I', data[pos:pos+4])[0]
            pos += 4
            result['literals'].append(f"// JerryScript 版本: {version}")
        
        # 提取所有字符串字面量（包括压缩的）
        strings = self._extract_strings(data, min_length=2)
        result['literals'] = strings[:100]  # 限制数量
        
        # 解析函数和字节码
        funcs = self._parse_jerryscript_functions(data)
        result['functions'] = funcs
        
        # 尝试还原 JavaScript 代码
        code = self._reconstruct_js_code(funcs, strings)
        result['code'] = code
        
        return result

    def _parse_jerryscript_functions(self, data: bytes) -> list:
        """解析 JerryScript 字节码中的函数"""
        functions = []
        pos = 0
        
        # 寻找可能的函数定义模式
        while pos < len(data) - 16:
            # 查找函数签名模式
            # 函数通常以特定的字节码序列开始
            if pos + 8 <= len(data):
                # 尝试识别函数结构
                maybe_func = self._try_parse_function(data, pos)
                if maybe_func:
                    functions.append(maybe_func)
                    pos += maybe_func.get('bytecode_len', 16)
                else:
                    pos += 1
            else:
                pos += 1
        
        return functions

    def _try_parse_function(self, data: bytes, pos: int) -> dict:
        """尝试解析单个函数"""
        func = {
            'name': '<anonymous>',
            'params': [],
            'locals': 0,
            'scope_depth': 0,
            'bytecode': [],
            'bytecode_len': 0
        }
        
        # 查找函数名（在字符串池附近）
        strings = self._extract_strings(data[pos:pos+128], min_length=1)
        if strings:
            # 第一个非数字字符串可能是函数名
            for s in strings:
                if s and not s[0].isdigit() and len(s) > 1:
                    func['name'] = s
                    break
        
        # 解析字节码指令
        bytecode_start = pos
        instrs = []
        
        while pos < len(data) - 2:
            opcode = data[pos]
            pos += 1
            
            if opcode == 0x00:  # EXT opcode
                if pos < len(data):
                    ext_opcode = data[pos]
                    pos += 1
                    instr_name = JERRYSCRIPT_EXT_OPCODES.get(ext_opcode, f'EXT_{ext_opcode:02x}')
                    # 解析扩展指令参数
                    args = self._parse_opcode_args(data, pos, ext_opcode)
                    instrs.append(f"{instr_name} {args}")
                    pos += len(args) // 2  # 粗略估计参数长度
            else:
                instr_name = JERRYSCRIPT_OPCODES.get(opcode, f'UNKNOWN_{opcode:02x}')
                # 解析参数
                args = self._parse_opcode_args(data, pos, opcode)
                instrs.append(f"{instr_name} {args}")
                pos += len(args) // 2
            
            # 遇到返回指令表示函数结束
            if opcode in [0x70, 0x71, 0x72, 0x73, 0x74]:  # RETURN 系列
                break
            
            # 限制指令数量
            if len(instrs) > 100:
                break
        
        func['bytecode'] = instrs
        func['bytecode_len'] = pos - bytecode_start
        
        # 从字节码中推断参数和本地变量数量
        func['params'] = self._infer_params(instrs)
        func['locals'] = self._count_locals(instrs)
        
        return func

    def _parse_opcode_args(self, data: bytes, pos: int, opcode: int) -> str:
        """解析指令参数"""
        args = []
        
        # 根据指令类型解析参数
        if opcode in [0xB0, 0xB1]:  # PUSH_LIT, PUSH_LIT_BYTE
            if pos < len(data):
                lit_idx = data[pos]
                args.append(f"literal[{lit_idx}]")
        elif opcode in [0x64, 0x65, 0x66]:  # CALL, CALL_EVAL, CALL_CONSTRUCTOR
            if pos < len(data):
                arg_count = data[pos]
                args.append(f"{arg_count} args")
        elif opcode in [0x77, 0x78, 0x79]:  # JMP, JMP_TRUE, JMP_FALSE
            if pos + 2 <= len(data):
                offset = struct.unpack('<h', data[pos:pos+2])[0]
                args.append(f"offset={offset}")
        elif 0xC0 <= opcode <= 0xC7:  # STORE_LOCAL 系列
            if pos < len(data):
                idx = data[pos]
                args.append(f"local[{idx}]")
        elif 0xB4 <= opcode <= 0xB7:  # PUSH_LOCAL 系列
            if pos < len(data):
                idx = data[pos]
                args.append(f"local[{idx}]")
        
        return ', '.join(args)

    def _infer_params(self, bytecode: list) -> list:
        """从字节码推断函数参数"""
        params = []
        param_count = 0
        
        for instr in bytecode:
            if 'PUSH_ARG' in instr:
                match = re.search(r'PUSH_ARG(?:_BYTE)?\s*(\d+)', instr)
                if match:
                    idx = int(match.group(1))
                    if idx >= param_count:
                        param_count = idx + 1
        
        for i in range(param_count):
            params.append(f'arg{i}')
        
        return params

    def _count_locals(self, bytecode: list) -> int:
        """统计本地变量数量"""
        max_local = 0
        
        for instr in bytecode:
            if 'STORE_LOCAL' in instr or 'PUSH_LOCAL' in instr:
                match = re.search(r'(?:STORE|PUSH)_LOCAL(?:_[A-Z_]+)?\s*(\d+)', instr)
                if match:
                    idx = int(match.group(1))
                    if idx > max_local:
                        max_local = idx
        
        return max_local + 1

    def _reconstruct_js_code(self, functions: list, strings: list) -> list:
        """尝试还原 JavaScript 代码"""
        code = []
        
        for func in functions:
            if not func['bytecode']:
                continue
            
            lines = []
            lines.append(f"function {func['name']}({', '.join(func['params'] or [])}) {{")
            
            # 初始化本地变量
            if func['locals'] > 0:
                lines.append(f"  var {' ,'.join(f'v{i}' for i in range(func['locals']))};")
            
            # 还原字节码指令为 JavaScript
            js_body = self._bytecode_to_js(func['bytecode'], strings)
            lines.extend([f"  {line}" for line in js_body])
            
            lines.append("}")
            code.extend(lines)
            code.append("")
        
        return code

    def _bytecode_to_js(self, bytecode: list, strings: list) -> list:
        """将字节码指令转换为 JavaScript"""
        lines = []
        stack = []
        
        for instr in bytecode:
            if instr.startswith('PUSH_LIT'):
                match = re.search(r'literal\[(\d+)\]', instr)
                if match and int(match.group(1)) < len(strings):
                    lit = strings[int(match.group(1))]
                    if lit.isdigit():
                        stack.append(lit)
                    else:
                        stack.append(f'"{lit}"')
            elif instr.startswith('PUSH_TRUE'):
                stack.append('true')
            elif instr.startswith('PUSH_FALSE'):
                stack.append('false')
            elif instr.startswith('PUSH_NULL'):
                stack.append('null')
            elif instr.startswith('PUSH_UNDEFINED'):
                stack.append('undefined')
            elif 'ADD' in instr and not instr.startswith('PUSH'):
                if len(stack) >= 2:
                    b = stack.pop()
                    a = stack.pop()
                    stack.append(f"({a} + {b})")
            elif 'SUB' in instr and not instr.startswith('PUSH'):
                if len(stack) >= 2:
                    b = stack.pop()
                    a = stack.pop()
                    stack.append(f"({a} - {b})")
            elif 'MUL' in instr and not instr.startswith('PUSH'):
                if len(stack) >= 2:
                    b = stack.pop()
                    a = stack.pop()
                    stack.append(f"({a} * {b})")
            elif 'DIV' in instr:
                if len(stack) >= 2:
                    b = stack.pop()
                    a = stack.pop()
                    stack.append(f"({a} / {b})")
            elif 'CALL' in instr:
                match = re.search(r'(\d+) args', instr)
                arg_count = int(match.group(1)) if match else 0
                args = []
                for _ in range(arg_count):
                    if stack:
                        args.insert(0, stack.pop())
                if stack:
                    func_name = stack.pop()
                    lines.append(f"{func_name}({', '.join(args)});")
            elif 'RETURN' in instr:
                if stack:
                    lines.append(f"return {stack.pop()};")
                else:
                    lines.append("return;")
            elif 'STORE_LOCAL' in instr:
                match = re.search(r'local\[(\d+)\]', instr)
                if match and stack:
                    val = stack.pop()
                    lines.append(f"v{match.group(1)} = {val};")
            elif 'GET_BY_STR_LIT' in instr:
                if len(stack) >= 2:
                    prop = stack.pop()
                    obj = stack.pop()
                    stack.append(f"{obj}[{prop}]")
            elif 'SET_BY_STR_LIT' in instr:
                if len(stack) >= 3:
                    val = stack.pop()
                    prop = stack.pop()
                    obj = stack.pop()
                    lines.append(f"{obj}[{prop}] = {val};")
        
        return lines

    def _decompile_generic(self,
                            filepath: str) -> Optional[str]:
        """通用反编译方法：尝试所有方法"""
        methods = [
            self._decompile_v8_snapshot,
            self._decompile_quickjs,
            self._decompile_jerryscript,
        ]

        for method in methods:
            try:
                result = method(filepath)
                if result and len(result) > 50:
                    return result
            except Exception:
                continue

        # 最后的手段：提取可读内容
        return self._extract_readable(filepath)

    def _extract_readable(self,
                           filepath: str) -> Optional[str]:
        """从二进制文件中提取可读内容"""
        with open(filepath, 'rb') as f:
            data = f.read()

        result = [
            f"// [通用提取模式]",
            f"// 文件大小: {len(data)} bytes",
            f"// 字节码类型: 未识别",
            "",
        ]

        # 提取可打印字符串
        strings = self._extract_strings(data, min_length=4)
        if strings:
            result.append("// === 提取的字符串 ===")
            for s in strings[:100]:
                result.append(f'"{s}"')
            result.append("")

        # 提取可能的 URL
        urls = self._extract_urls(data)
        if urls:
            result.append("// === 发现的 URL ===")
            for url in urls:
                result.append(url)
            result.append("")

        # 十六进制头部信息
        result.append("// === 文件头 (前 64 字节) ===")
        for i in range(0, min(64, len(data)), 16):
            hex_str = ' '.join(
                f'{b:02x}' for b in data[i:i+16]
            )
            ascii_str = ''.join(
                chr(b) if 32 <= b < 127 else '.'
                for b in data[i:i+16]
            )
            result.append(f"// {i:04x}: {hex_str:<48} {ascii_str}")

        return '\n'.join(result)

    def _extract_strings(self, data: bytes,
                          min_length: int = 3) -> list:
        """提取二进制数据中的可打印字符串"""
        strings = []
        current = []

        for byte in data:
            if 32 <= byte < 127:
                current.append(chr(byte))
            else:
                if len(current) >= min_length:
                    strings.append(''.join(current))
                current = []

        if len(current) >= min_length:
            strings.append(''.join(current))

        return strings

    def _extract_urls(self, data: bytes) -> list:
        """提取二进制数据中的 URL"""
        import re
        text = data.decode('ascii', errors='ignore')
        pattern = r'https?://[^\s<>"\')\]\\]+'
        return list(set(re.findall(pattern, text)))

    def _try_external_tool(self, tool_name: str,
                            filepath: str) -> Optional[str]:
        """尝试使用外部工具"""
        try:
            result = subprocess.run(
                [tool_name, filepath],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return None

    def _run_node_script(self, script: str) -> Optional[str]:
        """运行 Node.js 脚本"""
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.js', delete=False
            ) as f:
                f.write(script)
                script_path = f.name

            result = subprocess.run(
                [self.node_path, script_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            os.unlink(script_path)

            if result.returncode == 0:
                return result.stdout
            else:
                print(f"  Node.js 错误: {result.stderr}")
                return None

        except FileNotFoundError:
            print("  警告: 未找到 Node.js，"
                  "跳过 V8 反编译")
            return None
        except subprocess.TimeoutExpired:
            print("  警告: Node.js 脚本执行超时")
            return None
