#!/usr/bin/env python3
"""
JerryScript CBC Bytecode Decompiler
完整的JerryScript字节码反编译器

参考资料：
1. JerryScript Internals: https://github.com/jerryscript-project/jerryscript/blob/master/docs/04.INTERNALS.md
2. JerryScript Parser & VM: https://wiki.tizen.org/images/8/89/03-JerryScript_Parser_and_VM.pdf

字节码结构：
- Header (cbc_compiled_code)
- Literals (ecma_value数组)
- Bytecode Instructions

支持的指令参数类型：
- No arguments
- Literal argument
- Byte argument  
- Branch argument (1-3 bytes)
- Byte + Literal arguments
- Two literal arguments
- Three literal arguments
"""

import struct
import os
import re
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple


class CBCValueType(Enum):
    """ECMA值类型"""
    UNDEFINED = 0x00
    NULL = 0x01
    BOOLEAN = 0x02
    NUMBER = 0x03
    STRING = 0x04
    SYMBOL = 0x05
    OBJECT = 0x06
    FUNCTION = 0x07


# JerryScript CBC 指令定义（完整）
CBC_OPCODES = {
    0x00: 'EXT',  # Extended opcode
    
    # 算术运算
    0x01: ('NOP', 'no_args'),
    0x02: ('ADD', 'no_args'),
    0x03: ('SUB', 'no_args'),
    0x04: ('MUL', 'no_args'),
    0x05: ('DIV', 'no_args'),
    0x06: ('MOD', 'no_args'),
    0x07: ('EXP', 'no_args'),
    0x08: ('BIT_OR', 'no_args'),
    0x09: ('BIT_AND', 'no_args'),
    0x0A: ('BIT_XOR', 'no_args'),
    0x0B: ('SHL', 'no_args'),
    0x0C: ('SHR', 'no_args'),
    0x0D: ('SHR_U', 'no_args'),
    0x0E: ('ADD_I8', 'byte'),
    0x0F: ('ADD_I16', 'i16'),
    0x10: ('SUB_I8', 'byte'),
    0x11: ('SUB_I16', 'i16'),
    0x12: ('MUL_I8', 'byte'),
    0x13: ('MUL_I16', 'i16'),
    0x14: ('NEG', 'no_args'),
    0x15: ('NOT', 'no_args'),
    0x16: ('BIT_NOT', 'no_args'),
    0x17: ('INC', 'no_args'),
    0x18: ('DEC', 'no_args'),
    0x19: ('INC_I8', 'byte'),
    0x1A: ('INC_I16', 'i16'),
    0x1B: ('DEC_I8', 'byte'),
    0x1C: ('DEC_I16', 'i16'),
    
    # 类型检查
    0x1D: ('TYPEOF', 'no_args'),
    0x1E: ('INSTANCEOF', 'no_args'),
    0x1F: ('IN', 'no_args'),
    
    # 比较运算
    0x20: ('EQ', 'no_args'),
    0x21: ('NE', 'no_args'),
    0x22: ('STRICT_EQ', 'no_args'),
    0x23: ('STRICT_NE', 'no_args'),
    0x24: ('LT', 'no_args'),
    0x25: ('GT', 'no_args'),
    0x26: ('LE', 'no_args'),
    0x27: ('GE', 'no_args'),
    0x28: ('LT_NUM', 'no_args'),
    0x29: ('GT_NUM', 'no_args'),
    0x30: ('LE_NUM', 'no_args'),
    0x31: ('GE_NUM', 'no_args'),
    
    # 类型转换
    0x32: ('TO_NUMBER', 'no_args'),
    0x33: ('TO_INT32', 'no_args'),
    0x34: ('TO_UINT32', 'no_args'),
    0x35: ('TO_BOOLEAN', 'no_args'),
    0x36: ('TO_STRING', 'no_args'),
    0x37: ('TO_OBJECT', 'no_args'),
    0x38: ('TO_PRIMITIVE', 'no_args'),
    
    # 类型检查
    0x39: ('IS_FINITE', 'no_args'),
    0x3A: ('IS_NAN', 'no_args'),
    0x3B: ('IS_UNDEFINED', 'no_args'),
    0x3C: ('IS_NULL', 'no_args'),
    0x3D: ('IS_TRUE', 'no_args'),
    0x3E: ('IS_FALSE', 'no_args'),
    0x3F: ('IS_OBJECT', 'no_args'),
    0x40: ('IS_STRING', 'no_args'),
    0x41: ('IS_NUMBER', 'no_args'),
    0x42: ('IS_BOOLEAN', 'no_args'),
    0x43: ('IS_SYMBOL', 'no_args'),
    0x44: ('IS_FUNCTION', 'no_args'),
    
    # 对象操作
    0x45: ('NEW_OBJECT', 'no_args'),
    0x46: ('NEW_ARRAY', 'no_args'),
    0x47: ('NEW_REGEXP', 'no_args'),
    0x48: ('NEW_DATE', 'no_args'),
    0x49: ('NEW_ERROR', 'no_args'),
    0x4A: ('NEW_OBJECT_LITERAL', 'literal'),
    0x4B: ('NEW_ARRAY_LITERAL', 'literal'),
    
    # 属性访问
    0x4C: ('GET_BY_VAL', 'no_args'),
    0x4D: ('GET_BY_IDX', 'no_args'),
    0x4E: ('GET_BY_STR_LIT', 'literal'),
    0x4F: ('GET_BY_SYM', 'literal'),
    0x50: ('GET_BY_VAR', 'literal'),
    
    # 属性设置
    0x51: ('SET_BY_VAL', 'no_args'),
    0x52: ('SET_BY_IDX', 'no_args'),
    0x53: ('SET_BY_STR_LIT', 'literal'),
    0x54: ('SET_BY_SYM', 'literal'),
    0x55: ('SET_BY_VAR', 'literal'),
    0x56: ('SET_PROP', 'no_args'),
    0x57: ('SET_ELEM', 'no_args'),
    
    # 属性删除
    0x58: ('DELETE_BY_VAL', 'no_args'),
    0x59: ('DELETE_BY_IDX', 'no_args'),
    0x5A: ('DELETE_BY_STR_LIT', 'literal'),
    0x5B: ('DELETE_BY_SYM', 'literal'),
    
    # 增量/减量
    0x5C: ('INCREMENT_BY_VAL', 'no_args'),
    0x5D: ('DECREMENT_BY_VAL', 'no_args'),
    0x5E: ('INCREMENT_BY_IDX', 'no_args'),
    0x5F: ('DECREMENT_BY_IDX', 'no_args'),
    0x60: ('INCREMENT_BY_STR_LIT', 'literal'),
    0x61: ('DECREMENT_BY_STR_LIT', 'literal'),
    0x62: ('INCREMENT_BY_SYM', 'literal'),
    0x63: ('DECREMENT_BY_SYM', 'literal'),
    
    # 函数调用
    0x64: ('CALL', 'byte'),
    0x65: ('CALL_EVAL', 'byte'),
    0x66: ('CALL_CONSTRUCTOR', 'byte'),
    0x67: ('CALL_IMMEDIATE', 'literal_byte'),
    0x68: ('CALL_IMMEDIATE_0', 'literal'),
    0x69: ('CALL_IMMEDIATE_1', 'literal'),
    0x6A: ('CALL_IMMEDIATE_2', 'literal'),
    0x6B: ('CALL_IMMEDIATE_3', 'literal'),
    0x6C: ('CALL_IMMEDIATE_4', 'literal'),
    0x6D: ('CALL_ARG_0', 'no_args'),
    0x6E: ('CALL_ARG_1', 'no_args'),
    0x6F: ('CALL_ARG_2', 'no_args'),
    
    # 返回指令
    0x70: ('RETURN', 'no_args'),
    0x71: ('RETURN_UNDEFINED', 'no_args'),
    0x72: ('RETURN_FALSE', 'no_args'),
    0x73: ('RETURN_TRUE', 'no_args'),
    0x74: ('RETURN_NULL', 'no_args'),
    0x75: ('THROW', 'no_args'),
    0x76: ('THROW_LIT', 'literal'),
    
    # 跳转指令（分支参数）
    0x77: ('JMP', 'branch'),
    0x78: ('JMP_TRUE', 'branch'),
    0x79: ('JMP_FALSE', 'branch'),
    0x7A: ('JMP_UNDEFINED', 'branch'),
    0x7B: ('JMP_NULL', 'branch'),
    0x7C: ('JMP_NON_NULL', 'branch'),
    0x7D: ('JMP_NON_UNDEFINED', 'branch'),
    0x7E: ('JMP_REGEXP', 'branch'),
    0x7F: ('JMP_IN', 'branch'),
    0x80: ('JMP_INSTANCEOF', 'branch'),
    0x81: ('JMP_TYPEOF', 'branch'),
    0x82: ('JMP_DELETE_TRUE', 'branch'),
    0x83: ('JMP_DELETE_FALSE', 'branch'),
    0x84: ('JMP_NEG', 'branch'),
    0x85: ('JMP_ZERO', 'branch'),
    0x86: ('JMP_NON_ZERO', 'branch'),
    0x87: ('JMP_EQ', 'branch'),
    0x88: ('JMP_NE', 'branch'),
    0x89: ('JMP_STRICT_EQ', 'branch'),
    0x8A: ('JMP_STRICT_NE', 'branch'),
    0x8B: ('JMP_LT', 'branch'),
    0x8C: ('JMP_GT', 'branch'),
    0x8D: ('JMP_LE', 'branch'),
    0x8E: ('JMP_GE', 'branch'),
    0x8F: ('JMP_LT_NUM', 'branch'),
    0x90: ('JMP_GT_NUM', 'branch'),
    0x91: ('JMP_LE_NUM', 'branch'),
    0x92: ('JMP_GE_NUM', 'branch'),
    0x93: ('JMP_ADD', 'branch'),
    0x94: ('JMP_SUB', 'branch'),
    0x95: ('JMP_MUL', 'branch'),
    0x96: ('JMP_DIV', 'branch'),
    0x97: ('JMP_MOD', 'branch'),
    0x98: ('JMP_BIT_OR', 'branch'),
    0x99: ('JMP_BIT_AND', 'branch'),
    0x9A: ('JMP_BIT_XOR', 'branch'),
    0x9B: ('JMP_SHL', 'branch'),
    0x9C: ('JMP_SHR', 'branch'),
    0x9D: ('JMP_SHR_U', 'branch'),
    0x9E: ('JMP_INC', 'branch'),
    0x9F: ('JMP_DEC', 'branch'),
    
    # 压栈指令
    0xA0: ('PUSH_UNDEFINED', 'no_args'),
    0xA1: ('PUSH_NULL', 'no_args'),
    0xA2: ('PUSH_TRUE', 'no_args'),
    0xA3: ('PUSH_FALSE', 'no_args'),
    0xA4: ('PUSH_UNDEFINED_N', 'byte'),
    0xA5: ('PUSH_NULL_N', 'byte'),
    0xA6: ('PUSH_TRUE_N', 'byte'),
    0xA7: ('PUSH_FALSE_N', 'byte'),
    0xA8: ('PUSH_UNDEFINED_2', 'no_args'),
    0xA9: ('PUSH_NULL_2', 'no_args'),
    0xAA: ('PUSH_TRUE_2', 'no_args'),
    0xAB: ('PUSH_FALSE_2', 'no_args'),
    0xAC: ('PUSH_UNDEFINED_3', 'no_args'),
    0xAD: ('PUSH_NULL_3', 'no_args'),
    0xAE: ('PUSH_TRUE_3', 'no_args'),
    0xAF: ('PUSH_FALSE_3', 'no_args'),
    0xB0: ('PUSH_LIT', 'literal'),
    0xB1: ('PUSH_LIT_BYTE', 'byte'),
    0xB2: ('PUSH_CURR_CONTEXT', 'no_args'),
    0xB3: ('PUSH_ARG', 'no_args'),
    0xB4: ('PUSH_LOCAL', 'literal'),
    0xB5: ('PUSH_LOCAL_BYTE', 'byte'),
    0xB6: ('PUSH_LOCAL_I8', 'i8'),
    0xB7: ('PUSH_LOCAL_I16', 'i16'),
    0xB8: ('PUSH_GLOBAL', 'literal'),
    0xB9: ('PUSH_GLOBAL_BYTE', 'byte'),
    0xBA: ('PUSH_GLOBAL_I8', 'i8'),
    0xBB: ('PUSH_GLOBAL_I16', 'i16'),
    0xBC: ('PUSH_THIS', 'no_args'),
    0xBD: ('PUSH_HOLE', 'no_args'),
    0xBE: ('PUSH_ARG_COUNT', 'no_args'),
    0xBF: ('PUSH_UNDEFINED_ARG', 'no_args'),
    
    # 存储指令
    0xC0: ('STORE_LOCAL', 'literal'),
    0xC1: ('STORE_LOCAL_BYTE', 'byte'),
    0xC2: ('STORE_LOCAL_I8', 'i8'),
    0xC3: ('STORE_LOCAL_I16', 'i16'),
    0xC4: ('STORE_GLOBAL', 'literal'),
    0xC5: ('STORE_GLOBAL_BYTE', 'byte'),
    0xC6: ('STORE_GLOBAL_I8', 'i8'),
    0xC7: ('STORE_GLOBAL_I16', 'i16'),
    0xC8: ('STORE_ARG', 'literal'),
    0xC9: ('STORE_ARG_BYTE', 'byte'),
    0xCA: ('STORE_ARG_I8', 'i8'),
    0xCB: ('STORE_ARG_I16', 'i16'),
    0xCC: ('STORE_THIS', 'no_args'),
    
    # 栈操作
    0xCD: ('POP', 'no_args'),
    0xCE: ('POP_N', 'byte'),
    0xCF: ('POP_2', 'no_args'),
    0xD0: ('POP_3', 'no_args'),
    0xD1: ('POP_N_2', 'byte'),
    0xD2: ('POP_N_3', 'byte'),
    0xD3: ('DUP', 'no_args'),
    0xD4: ('DUP_2', 'no_args'),
    0xD5: ('DUP_3', 'no_args'),
    0xD6: ('SWAP', 'no_args'),
    0xD7: ('SWAP_2', 'no_args'),
    0xD8: ('SWAP_3', 'no_args'),
    0xD9: ('ROT', 'no_args'),
    0xDA: ('ROT_2', 'no_args'),
    0xDB: ('ROT_3', 'no_args'),
    
    # 复制指令
    0xDC: ('COPY_TO_LOCAL', 'literal'),
    0xDD: ('COPY_FROM_LOCAL', 'literal'),
    0xDE: ('COPY_TO_LOCAL_BYTE', 'byte'),
    0xDF: ('COPY_FROM_LOCAL_BYTE', 'byte'),
    0xE0: ('COPY_TO_LOCAL_I8', 'i8'),
    0xE1: ('COPY_FROM_LOCAL_I8', 'i8'),
    0xE2: ('COPY_TO_LOCAL_I16', 'i16'),
    0xE3: ('COPY_FROM_LOCAL_I16', 'i16'),
    0xE4: ('COPY_TO_ARG', 'literal'),
    0xE5: ('COPY_FROM_ARG', 'literal'),
    0xE6: ('COPY_TO_ARG_BYTE', 'byte'),
    0xE7: ('COPY_FROM_ARG_BYTE', 'byte'),
    0xE8: ('COPY_TO_ARG_I8', 'i8'),
    0xE9: ('COPY_FROM_ARG_I8', 'i8'),
    0xEA: ('COPY_TO_ARG_I16', 'i16'),
    0xEB: ('COPY_FROM_ARG_I16', 'i16'),
    0xEC: ('COPY_TO_GLOBAL', 'literal'),
    0xED: ('COPY_FROM_GLOBAL', 'literal'),
    0xEE: ('COPY_TO_GLOBAL_BYTE', 'byte'),
    0xEF: ('COPY_FROM_GLOBAL_BYTE', 'byte'),
    0xF0: ('COPY_TO_GLOBAL_I8', 'i8'),
    0xF1: ('COPY_FROM_GLOBAL_I8', 'i8'),
    0xF2: ('COPY_TO_GLOBAL_I16', 'i16'),
    0xF3: ('COPY_FROM_GLOBAL_I16', 'i16'),
    0xF4: ('COPY_TO_THIS', 'no_args'),
    0xF5: ('COPY_FROM_THIS', 'no_args'),
    
    # 延迟操作
    0xF6: ('DEFERRED', 'no_args'),
    0xF7: ('DEFERRED_BRANCH', 'no_args'),
    0xF8: ('DEFERRED_CALL', 'no_args'),
    0xF9: ('DEFERRED_CALL_0', 'no_args'),
    0xFA: ('DEFERRED_CALL_1', 'no_args'),
    0xFB: ('DEFERRED_CALL_2', 'no_args'),
    0xFC: ('DEFERRED_CALL_3', 'no_args'),
    0xFD: ('DEFERRED_CALL_4', 'no_args'),
    0xFE: ('DEFERRED_CONSTRUCTOR', 'no_args'),
    0xFF: ('DEFERRED_EVAL', 'no_args'),
}

# 扩展指令
CBC_EXT_OPCODES = {
    0x00: ('EXT_DEBUGGER', 'no_args'),
    0x01: ('EXT_WITH_CREATE_CONTEXT', 'branch'),
    0x02: ('EXT_WITH_DELETE_CONTEXT', 'no_args'),
    0x03: ('EXT_CATCH_CREATE_CONTEXT', 'branch'),
    0x04: ('EXT_CATCH_DELETE_CONTEXT', 'no_args'),
    0x05: ('EXT_CLOSE', 'no_args'),
    0x06: ('EXT_NEW_FUNCTION', 'literal'),
    0x07: ('EXT_GET_BY_INDEX_SHORT', 'no_args'),
    0x08: ('EXT_SET_BY_INDEX_SHORT', 'no_args'),
    0x09: ('EXT_DELETE_BY_INDEX_SHORT', 'no_args'),
    0x0A: ('EXT_INCREMENT_BY_INDEX_SHORT', 'no_args'),
    0x0B: ('EXT_DECREMENT_BY_INDEX_SHORT', 'no_args'),
    
    # 短跳转指令
    0x0C: ('EXT_JMP_BYTE', 'byte'),
    0x0D: ('EXT_JMP_TRUE_BYTE', 'byte'),
    0x0E: ('EXT_JMP_FALSE_BYTE', 'byte'),
    0x0F: ('EXT_JMP_UNDEFINED_BYTE', 'byte'),
    0x10: ('EXT_JMP_NULL_BYTE', 'byte'),
    0x11: ('EXT_JMP_NON_NULL_BYTE', 'byte'),
    0x12: ('EXT_JMP_NON_UNDEFINED_BYTE', 'byte'),
    0x13: ('EXT_JMP_REGEXP_BYTE', 'byte'),
    0x14: ('EXT_JMP_IN_BYTE', 'byte'),
    0x15: ('EXT_JMP_INSTANCEOF_BYTE', 'byte'),
    0x16: ('EXT_JMP_TYPEOF_BYTE', 'byte'),
    0x17: ('EXT_JMP_DELETE_TRUE_BYTE', 'byte'),
    0x18: ('EXT_JMP_DELETE_FALSE_BYTE', 'byte'),
    0x19: ('EXT_JMP_NEG_BYTE', 'byte'),
    0x20: ('EXT_JMP_ZERO_BYTE', 'byte'),
    0x21: ('EXT_JMP_NON_ZERO_BYTE', 'byte'),
    0x22: ('EXT_JMP_EQ_BYTE', 'byte'),
    0x23: ('EXT_JMP_NE_BYTE', 'byte'),
    0x24: ('EXT_JMP_STRICT_EQ_BYTE', 'byte'),
    0x25: ('EXT_JMP_STRICT_NE_BYTE', 'byte'),
    0x26: ('EXT_JMP_LT_BYTE', 'byte'),
    0x27: ('EXT_JMP_GT_BYTE', 'byte'),
    0x28: ('EXT_JMP_LE_BYTE', 'byte'),
    0x29: ('EXT_JMP_GE_BYTE', 'byte'),
    0x30: ('EXT_JMP_LT_NUM_BYTE', 'byte'),
    0x31: ('EXT_JMP_GT_NUM_BYTE', 'byte'),
    0x32: ('EXT_JMP_LE_NUM_BYTE', 'byte'),
    0x33: ('EXT_JMP_GE_NUM_BYTE', 'byte'),
    
    # 常量压栈
    0x34: ('EXT_PUSH_INT8', 'i8'),
    0x35: ('EXT_PUSH_INT16', 'i16'),
    0x36: ('EXT_PUSH_INT32', 'i32'),
    0x37: ('EXT_PUSH_DOUBLE', 'double'),
    0x38: ('EXT_PUSH_FLOAT32', 'float'),
    
    # 立即数运算
    0x39: ('EXT_ADD_INT8', 'i8'),
    0x3A: ('EXT_ADD_INT16', 'i16'),
    0x3B: ('EXT_SUB_INT8', 'i8'),
    0x3C: ('EXT_SUB_INT16', 'i16'),
    0x3D: ('EXT_MUL_INT8', 'i8'),
    0x3E: ('EXT_MUL_INT16', 'i16'),
    0x3F: ('EXT_INC_INT8', 'i8'),
    0x40: ('EXT_INC_INT16', 'i16'),
    0x41: ('EXT_DEC_INT8', 'i8'),
    0x42: ('EXT_DEC_INT16', 'i16'),
    
    # 上下文操作
    0x43: ('EXT_PUSH_CONTEXT', 'no_args'),
    0x44: ('EXT_PUSH_ARG_N', 'byte'),
    0x45: ('EXT_STORE_ARG_N', 'byte'),
    0x46: ('EXT_COPY_TO_ARG_N', 'byte'),
    0x47: ('EXT_COPY_FROM_ARG_N', 'byte'),
    0x48: ('EXT_CALL_ARG_N', 'byte'),
    0x49: ('EXT_CALL_IMMEDIATE_ARG_N', 'literal_byte'),
    
    # 字符串字面量快速访问
    0x4A: ('EXT_GET_BY_STR_LIT_SHORT', 'byte'),
    0x4B: ('EXT_SET_BY_STR_LIT_SHORT', 'byte'),
    0x4C: ('EXT_DELETE_BY_STR_LIT_SHORT', 'byte'),
    0x4D: ('EXT_INCREMENT_BY_STR_LIT_SHORT', 'byte'),
    0x4E: ('EXT_DECREMENT_BY_STR_LIT_SHORT', 'byte'),
    
    # 符号快速访问
    0x4F: ('EXT_GET_BY_SYM_SHORT', 'byte'),
    0x50: ('EXT_SET_BY_SYM_SHORT', 'byte'),
    0x51: ('EXT_DELETE_BY_SYM_SHORT', 'byte'),
    0x52: ('EXT_INCREMENT_BY_SYM_SHORT', 'byte'),
    0x53: ('EXT_DECREMENT_BY_SYM_SHORT', 'byte'),
    
    # 字节索引版本
    0x54: ('EXT_GET_BY_STR_LIT_BYTE', 'byte'),
    0x55: ('EXT_SET_BY_STR_LIT_BYTE', 'byte'),
    0x56: ('EXT_DELETE_BY_STR_LIT_BYTE', 'byte'),
    0x57: ('EXT_INCREMENT_BY_STR_LIT_BYTE', 'byte'),
    0x58: ('EXT_DECREMENT_BY_STR_LIT_BYTE', 'byte'),
    0x59: ('EXT_GET_BY_SYM_BYTE', 'byte'),
    0x5A: ('EXT_SET_BY_SYM_BYTE', 'byte'),
    0x5B: ('EXT_DELETE_BY_SYM_BYTE', 'byte'),
    0x5C: ('EXT_INCREMENT_BY_SYM_BYTE', 'byte'),
    0x5D: ('EXT_DECREMENT_BY_SYM_BYTE', 'byte'),
    
    # 控制流结构
    0x5E: ('EXT_FOR_IN', 'branch'),
    0x5F: ('EXT_FOR_OF', 'branch'),
    0x60: ('EXT_FOR_OF_NEXT', 'no_args'),
    0x61: ('EXT_WHILE', 'branch'),
    0x62: ('EXT_WHILE_NEXT', 'no_args'),
    0x63: ('EXT_DO_WHILE', 'branch'),
    0x64: ('EXT_FOR', 'branch'),
    0x65: ('EXT_FOR_NEXT', 'no_args'),
    0x66: ('EXT_IF', 'branch'),
    0x67: ('EXT_IF_ELSE', 'branch'),
    0x68: ('EXT_TRY_FINALLY', 'branch'),
    0x69: ('EXT_TRY_CATCH', 'branch'),
    0x6A: ('EXT_TRY_CATCH_FINALLY', 'branch'),
    0x6B: ('EXT_WITH', 'branch'),
    0x6C: ('EXT_SWITCH', 'literal'),
    0x6D: ('EXT_DEBUGGER_STATEMENT', 'no_args'),
    
    # 内置对象操作
    0x6E: ('EXT_PUSH_BUILTIN', 'byte'),
    0x6F: ('EXT_NEW_BUILTIN', 'byte'),
    0x70: ('EXT_NEW_BUILTIN_ARG_0', 'byte'),
    0x71: ('EXT_NEW_BUILTIN_ARG_1', 'byte'),
    0x72: ('EXT_NEW_BUILTIN_ARG_2', 'byte'),
    0x73: ('EXT_NEW_BUILTIN_ARG_3', 'byte'),
    0x74: ('EXT_NEW_BUILTIN_ARG_4', 'byte'),
    0x75: ('EXT_CALL_BUILTIN', 'byte'),
    0x76: ('EXT_CALL_BUILTIN_0', 'byte'),
    0x77: ('EXT_CALL_BUILTIN_1', 'byte'),
    0x78: ('EXT_CALL_BUILTIN_2', 'byte'),
    0x79: ('EXT_CALL_BUILTIN_3', 'byte'),
    0x7A: ('EXT_CALL_BUILTIN_4', 'byte'),
    0x7B: ('EXT_CALL_BUILTIN_ARG_N', 'byte_byte'),
    
    # 内置属性操作
    0x7C: ('EXT_GET_BUILTIN_PROPERTY', 'byte_byte'),
    0x7D: ('EXT_SET_BUILTIN_PROPERTY', 'byte_byte'),
    0x7E: ('EXT_DELETE_BUILTIN_PROPERTY', 'byte_byte'),
    0x7F: ('EXT_INCREMENT_BUILTIN_PROPERTY', 'byte_byte'),
    0x80: ('EXT_DECREMENT_BUILTIN_PROPERTY', 'byte_byte'),
    
    # RegExp 属性操作
    0x81: ('EXT_GET_REGEXP_PROPERTY', 'byte'),
    0x82: ('EXT_SET_REGEXP_PROPERTY', 'byte'),
    0x83: ('EXT_DELETE_REGEXP_PROPERTY', 'byte'),
    0x84: ('EXT_INCREMENT_REGEXP_PROPERTY', 'byte'),
    0x85: ('EXT_DECREMENT_REGEXP_PROPERTY', 'byte'),
    
    # 跳转表
    0x86: ('EXT_JMP_TABLE', 'literal'),
    0x87: ('EXT_JMP_TABLE_BYTE', 'byte'),
    
    # RegExp 结果
    0x88: ('EXT_PUSH_REGEXP_RESULT', 'no_args'),
    0x89: ('EXT_PUSH_REGEXP_RESULT_INDEX', 'literal'),
    0x8A: ('EXT_PUSH_REGEXP_RESULT_INDEX_BYTE', 'byte'),
    0x8B: ('EXT_PUSH_REGEXP_RESULT_VALUE', 'literal'),
    0x8C: ('EXT_PUSH_REGEXP_RESULT_VALUE_BYTE', 'byte'),
    
    # RegExp 操作
    0x8D: ('EXT_REGEXP_EXEC', 'no_args'),
    0x8E: ('EXT_REGEXP_TEST', 'no_args'),
    0x8F: ('EXT_REGEXP_MATCH', 'no_args'),
    0x90: ('EXT_REGEXP_SEARCH', 'no_args'),
    0x91: ('EXT_REGEXP_REPLACE', 'no_args'),
    0x92: ('EXT_REGEXP_SPLIT', 'no_args'),
    
    # 字符串方法
    0x93: ('EXT_STRING_INDEXOF', 'no_args'),
    0x94: ('EXT_STRING_LASTINDEXOF', 'no_args'),
    0x95: ('EXT_STRING_CHARAT', 'no_args'),
    0x96: ('EXT_STRING_CHARCODEAT', 'no_args'),
    0x97: ('EXT_STRING_CONCAT', 'no_args'),
    0x98: ('EXT_STRING_SLICE', 'no_args'),
    0x99: ('EXT_STRING_SUBSTRING', 'no_args'),
    0x9A: ('EXT_STRING_SUBSTR', 'no_args'),
    0x9B: ('EXT_STRING_TOLOWERCASE', 'no_args'),
    0x9C: ('EXT_STRING_TOUPPERCASE', 'no_args'),
    0x9D: ('EXT_STRING_TRIM', 'no_args'),
    0x9E: ('EXT_STRING_TRIMSTART', 'no_args'),
    0x9F: ('EXT_STRING_TRIMEND', 'no_args'),
    0xA0: ('EXT_STRING_STARTSWITH', 'no_args'),
    0xA1: ('EXT_STRING_ENDSWITH', 'no_args'),
    0xA2: ('EXT_STRING_INCLUDES', 'no_args'),
    0xA3: ('EXT_STRING_REPEAT', 'no_args'),
    0xA4: ('EXT_STRING_PADSTART', 'no_args'),
    0xA5: ('EXT_STRING_PADEND', 'no_args'),
    
    # 数组方法
    0xA6: ('EXT_ARRAY_PUSH', 'no_args'),
    0xA7: ('EXT_ARRAY_POP', 'no_args'),
    0xA8: ('EXT_ARRAY_SHIFT', 'no_args'),
    0xA9: ('EXT_ARRAY_UNSHIFT', 'no_args'),
    0xAA: ('EXT_ARRAY_SPLICE', 'no_args'),
    0xAB: ('EXT_ARRAY_SLICE', 'no_args'),
    0xAC: ('EXT_ARRAY_CONCAT', 'no_args'),
    0xAD: ('EXT_ARRAY_JOIN', 'no_args'),
    0xAE: ('EXT_ARRAY_INDEXOF', 'no_args'),
    0xAF: ('EXT_ARRAY_LASTINDEXOF', 'no_args'),
    0xB0: ('EXT_ARRAY_INCLUDES', 'no_args'),
    0xB1: ('EXT_ARRAY_REVERSE', 'no_args'),
    0xB2: ('EXT_ARRAY_SORT', 'no_args'),
    0xB3: ('EXT_ARRAY_MAP', 'no_args'),
    0xB4: ('EXT_ARRAY_FILTER', 'no_args'),
    0xB5: ('EXT_ARRAY_REDUCE', 'no_args'),
    0xB6: ('EXT_ARRAY_REDUCE_RIGHT', 'no_args'),
    0xB7: ('EXT_ARRAY_FOR_EACH', 'no_args'),
    0xB8: ('EXT_ARRAY_EVERY', 'no_args'),
    0xB9: ('EXT_ARRAY_SOME', 'no_args'),
    0xBA: ('EXT_ARRAY_FIND', 'no_args'),
    0xBB: ('EXT_ARRAY_FIND_INDEX', 'no_args'),
    0xBC: ('EXT_ARRAY_FILL', 'no_args'),
    0xBD: ('EXT_ARRAY_COPY_WITHIN', 'no_args'),
    
    # Date 方法
    0xBE: ('EXT_DATE_GET_FULL_YEAR', 'no_args'),
    0xBF: ('EXT_DATE_GET_MONTH', 'no_args'),
    0xC0: ('EXT_DATE_GET_DATE', 'no_args'),
    0xC1: ('EXT_DATE_GET_DAY', 'no_args'),
    0xC2: ('EXT_DATE_GET_HOURS', 'no_args'),
    0xC3: ('EXT_DATE_GET_MINUTES', 'no_args'),
    0xC4: ('EXT_DATE_GET_SECONDS', 'no_args'),
    0xC5: ('EXT_DATE_GET_MILLISECONDS', 'no_args'),
    0xC6: ('EXT_DATE_GET_TIME', 'no_args'),
    0xC7: ('EXT_DATE_GET_TIMEZONE_OFFSET', 'no_args'),
    0xC8: ('EXT_DATE_GET_UTC_FULL_YEAR', 'no_args'),
    0xC9: ('EXT_DATE_GET_UTC_MONTH', 'no_args'),
    0xCA: ('EXT_DATE_GET_UTC_DATE', 'no_args'),
    0xCB: ('EXT_DATE_GET_UTC_DAY', 'no_args'),
    0xCC: ('EXT_DATE_GET_UTC_HOURS', 'no_args'),
    0xCD: ('EXT_DATE_GET_UTC_MINUTES', 'no_args'),
    0xCE: ('EXT_DATE_GET_UTC_SECONDS', 'no_args'),
    0xCF: ('EXT_DATE_GET_UTC_MILLISECONDS', 'no_args'),
    0xD0: ('EXT_DATE_SET_FULL_YEAR', 'no_args'),
    0xD1: ('EXT_DATE_SET_MONTH', 'no_args'),
    0xD2: ('EXT_DATE_SET_DATE', 'no_args'),
    0xD3: ('EXT_DATE_SET_HOURS', 'no_args'),
    0xD4: ('EXT_DATE_SET_MINUTES', 'no_args'),
    0xD5: ('EXT_DATE_SET_SECONDS', 'no_args'),
    0xD6: ('EXT_DATE_SET_MILLISECONDS', 'no_args'),
    0xD7: ('EXT_DATE_SET_TIME', 'no_args'),
    0xD8: ('EXT_DATE_SET_UTC_FULL_YEAR', 'no_args'),
    0xD9: ('EXT_DATE_SET_UTC_MONTH', 'no_args'),
    0xDA: ('EXT_DATE_SET_UTC_DATE', 'no_args'),
    0xDB: ('EXT_DATE_SET_UTC_HOURS', 'no_args'),
    0xDC: ('EXT_DATE_SET_UTC_MINUTES', 'no_args'),
    0xDD: ('EXT_DATE_SET_UTC_SECONDS', 'no_args'),
    0xDE: ('EXT_DATE_SET_UTC_MILLISECONDS', 'no_args'),
    0xDF: ('EXT_DATE_TO_STRING', 'no_args'),
    0xE0: ('EXT_DATE_TO_LOCALE_STRING', 'no_args'),
    0xE1: ('EXT_DATE_TO_GMT_STRING', 'no_args'),
    0xE2: ('EXT_DATE_TO_ISO_STRING', 'no_args'),
    0xE3: ('EXT_DATE_GET_TIME', 'no_args'),
    
    # Object 方法
    0xE4: ('EXT_OBJECT_ASSIGN', 'no_args'),
    0xE5: ('EXT_OBJECT_CREATE', 'no_args'),
    0xE6: ('EXT_OBJECT_DEFINE_PROPERTY', 'no_args'),
    0xE7: ('EXT_OBJECT_DELETE_PROPERTY', 'no_args'),
    0xE8: ('EXT_OBJECT_FREEZE', 'no_args'),
    0xE9: ('EXT_OBJECT_GET_OWN_PROPERTY_DESCRIPTOR', 'no_args'),
    0xEA: ('EXT_OBJECT_GET_PROTOTYPE_OF', 'no_args'),
    0xEB: ('EXT_OBJECT_HAS_OWN_PROPERTY', 'no_args'),
    0xEC: ('EXT_OBJECT_IS_FROZEN', 'no_args'),
    0xED: ('EXT_OBJECT_IS_SEALED', 'no_args'),
    0xEE: ('EXT_OBJECT_PREVENT_EXTENSIONS', 'no_args'),
    0xEF: ('EXT_OBJECT_SEAL', 'no_args'),
    0xF0: ('EXT_OBJECT_TO_STRING', 'no_args'),
    0xF1: ('EXT_FUNCTION_TO_STRING', 'no_args'),
    0xF2: ('EXT_ERROR_TO_STRING', 'no_args'),
    0xF3: ('EXT_NUMBER_TO_STRING', 'no_args'),
    0xF4: ('EXT_BOOLEAN_TO_STRING', 'no_args'),
    0xF5: ('EXT_SYMBOL_TO_STRING', 'no_args'),
    
    # 全局函数
    0xF6: ('EXT_JSON_STRINGIFY', 'no_args'),
    0xF7: ('EXT_JSON_PARSE', 'no_args'),
    0xF8: ('EXT_PARSE_FLOAT', 'no_args'),
    0xF9: ('EXT_PARSE_INT', 'no_args'),
    0xFA: ('EXT_IS_ARRAY', 'no_args'),
    0xFB: ('EXT_IS_FINITE', 'no_args'),
    0xFC: ('EXT_IS_NAN', 'no_args'),
    0xFD: ('EXT_DECODE_URI', 'no_args'),
    0xFE: ('EXT_DECODE_URI_COMPONENT', 'no_args'),
    0xFF: ('EXT_ENCODE_URI', 'no_args'),
}


class CBCHeader:
    """CBC 字节码头部结构"""
    def __init__(self):
        self.magic = b''
        self.version = 0
        self.flags = 0
        self.stack_limit = 0
        self.argument_end = 0
        self.register_end = 0
        self.ident_end = 0
        self.literal_end = 0
        self.code_start = 0
    
    def __repr__(self):
        return f"CBCHeader(version={self.version}, stack_limit={self.stack_limit}, " \
               f"args={self.argument_end}, registers={self.register_end}, " \
               f"literals={self.literal_end})"


class CBCLiteral:
    """CBC 字面量"""
    def __init__(self, index: int, value_type: CBCValueType, value):
        self.index = index
        self.type = value_type
        self.value = value
    
    def __repr__(self):
        return f"CBCToken({self.index}, {self.type.name}, {repr(self.value)[:50]})"


class CBCInstruction:
    """CBC 指令"""
    def __init__(self, offset: int, opcode: int, name: str, args: List[Any]):
        self.offset = offset
        self.opcode = opcode
        self.name = name
        self.args = args
    
    def __repr__(self):
        args_str = ', '.join(str(a) for a in self.args)
        return f"CBCInstruction({self.offset:04x}, {self.name} {args_str})"


class JerryScriptDecompiler:
    """完整的 JerryScript CBC 字节码反编译器"""
    
    def __init__(self):
        self.data = b''
        self.header = CBCHeader()
        self.literals = []
        self.instructions = []
        self.functions = []
    
    def decompile(self, filepath: str) -> str:
        """反编译 JerryScript CBC 字节码文件"""
        with open(filepath, 'rb') as f:
            self.data = f.read()
        
        self._parse_header()
        self._parse_literals()
        self._parse_instructions()
        self._parse_functions()
        
        return self._generate_code()
    
    def _parse_header(self):
        """解析 CBC 字节码头部"""
        pos = 0
        
        # 检查魔数
        if self.data.startswith(b'JS\x00\x00'):
            self.header.magic = b'JS\x00\x00'
            pos += 4
        elif self.data.startswith(b'\x01\x00'):
            self.header.magic = b'\x01\x00'
            pos += 2
        else:
            # 尝试自动检测
            pos = 0
        
        # 解析头部字段 (little-endian)
        if pos + 8 <= len(self.data):
            self.header.version = struct.unpack('<I', self.data[pos:pos+4])[0]
            pos += 4
            self.header.flags = struct.unpack('<I', self.data[pos:pos+4])[0]
            pos += 4
        
        if pos + 16 <= len(self.data):
            self.header.stack_limit = struct.unpack('<H', self.data[pos:pos+2])[0]
            pos += 2
            self.header.argument_end = struct.unpack('<H', self.data[pos:pos+2])[0]
            pos += 2
            self.header.register_end = struct.unpack('<H', self.data[pos:pos+2])[0]
            pos += 2
            self.header.ident_end = struct.unpack('<H', self.data[pos:pos+2])[0]
            pos += 2
            self.header.literal_end = struct.unpack('<H', self.data[pos:pos+2])[0]
            pos += 2
        
        self.header.code_start = pos
    
    def _parse_literals(self):
        """解析字面量池"""
        pos = self.header.code_start
        
        # 如果没有明确的字面量计数，尝试提取字符串
        if self.header.literal_end == 0:
            strings = self._extract_all_strings()
            for i, s in enumerate(strings[:200]):
                self.literals.append(CBCLiteral(i, CBCValueType.STRING, s))
            return
        
        # 解析结构化字面量
        for i in range(self.header.literal_end):
            if pos + 2 > len(self.data):
                break
            
            # 读取类型标签
            type_tag = self.data[pos]
            pos += 1
            
            value_type = self._parse_type_tag(type_tag)
            
            # 解析值
            value = self._parse_literal_value(type_tag, pos)
            pos += self._get_literal_size(type_tag, pos)
            
            self.literals.append(CBCLiteral(i, value_type, value))
    
    def _parse_type_tag(self, tag: int) -> CBCValueType:
        """解析类型标签"""
        type_map = {
            0x00: CBCValueType.UNDEFINED,
            0x01: CBCValueType.NULL,
            0x02: CBCValueType.BOOLEAN,
            0x03: CBCValueType.NUMBER,
            0x04: CBCValueType.STRING,
            0x05: CBCValueType.SYMBOL,
            0x06: CBCValueType.OBJECT,
            0x07: CBCValueType.FUNCTION,
        }
        return type_map.get(tag & 0x0F, CBCValueType.STRING)
    
    def _parse_literal_value(self, type_tag: int, pos: int):
        """解析字面量值"""
        base_type = type_tag & 0x0F
        
        if base_type == 0x00:  # UNDEFINED
            return None
        elif base_type == 0x01:  # NULL
            return None
        elif base_type == 0x02:  # BOOLEAN
            return bool(self.data[pos])
        elif base_type == 0x03:  # NUMBER
            if pos + 8 <= len(self.data):
                return struct.unpack('<d', self.data[pos:pos+8])[0]
            return 0.0
        elif base_type in (0x04, 0x05):  # STRING/SYMBOL
            return self._parse_string(pos)
        else:
            return f"<object_{type_tag}>"
    
    def _parse_string(self, pos: int) -> str:
        """解析字符串"""
        try:
            # 尝试多种字符串格式
            # 格式1: length (1-4 bytes) + string
            if pos + 2 <= len(self.data):
                length = self.data[pos]
                pos += 1
                if length == 0:
                    length = struct.unpack('<I', self.data[pos:pos+4])[0]
                    pos += 4
                
                if pos + length <= len(self.data):
                    return self.data[pos:pos+length].decode('utf-8', errors='replace')
            
            # 格式2: 以 null 结尾的字符串
            end_pos = self.data.find(b'\x00', pos)
            if end_pos != -1 and end_pos - pos < 500:
                return self.data[pos:end_pos].decode('utf-8', errors='replace')
        
        except Exception:
            pass
        
        return ""
    
    def _get_literal_size(self, type_tag: int, pos: int) -> int:
        """获取字面量大小"""
        base_type = type_tag & 0x0F
        
        if base_type in (0x00, 0x01):  # UNDEFINED, NULL
            return 0
        elif base_type == 0x02:  # BOOLEAN
            return 1
        elif base_type == 0x03:  # NUMBER
            return 8
        elif base_type in (0x04, 0x05):  # STRING, SYMBOL
            length = self.data[pos]
            if length == 0:
                return 4 + struct.unpack('<I', self.data[pos:pos+4])[0]
            return 1 + length
        else:
            return 4
    
    def _extract_all_strings(self) -> List[str]:
        """提取所有可打印字符串"""
        strings = []
        current = []
        
        for byte in self.data:
            if 32 <= byte < 127:
                current.append(chr(byte))
            else:
                if len(current) >= 2:
                    s = ''.join(current)
                    # 过滤纯数字和无意义字符串
                    if not s.isdigit() and len(s) >= 2:
                        strings.append(s)
                current = []
        
        if len(current) >= 2:
            s = ''.join(current)
            if not s.isdigit():
                strings.append(s)
        
        # 去重并排序
        return sorted(set(strings), key=lambda x: (-len(x), x))
    
    def _parse_instructions(self):
        """解析字节码指令"""
        pos = self.header.code_start
        
        # 如果有字面量，跳过它们
        if self.header.literal_end > 0:
            for lit in self.literals:
                if lit.type == CBCValueType.STRING:
                    pos += len(lit.value) + 1
        
        # 如果无法确定，从文件开头搜索
        if pos >= len(self.data):
            pos = 0
        
        # 解析指令直到文件结束
        while pos < len(self.data) - 1:
            offset = pos
            opcode = self.data[pos]
            pos += 1
            
            if opcode == 0x00:  # 扩展指令
                if pos >= len(self.data):
                    break
                ext_opcode = self.data[pos]
                pos += 1
                
                if ext_opcode in CBC_EXT_OPCODES:
                    name, arg_type = CBC_EXT_OPCODES[ext_opcode]
                else:
                    name = f'EXT_UNKNOWN_{ext_opcode:02x}'
                    arg_type = 'no_args'
            else:
                if opcode in CBC_OPCODES:
                    name, arg_type = CBC_OPCODES[opcode]
                else:
                    name = f'UNKNOWN_{opcode:02x}'
                    arg_type = 'no_args'
            
            # 解析参数
            args = self._parse_arguments(arg_type, pos)
            pos += self._get_argument_size(arg_type, pos)
            
            self.instructions.append(CBCInstruction(offset, opcode, name, args))
    
    def _parse_arguments(self, arg_type: str, pos: int) -> List[Any]:
        """解析指令参数"""
        args = []
        
        try:
            if arg_type == 'no_args':
                pass
            elif arg_type == 'byte':
                if pos < len(self.data):
                    args.append(self.data[pos])
            elif arg_type == 'i8':
                if pos < len(self.data):
                    args.append(struct.unpack('<b', self.data[pos:pos+1])[0])
            elif arg_type == 'i16':
                if pos + 2 <= len(self.data):
                    args.append(struct.unpack('<h', self.data[pos:pos+2])[0])
            elif arg_type == 'i32':
                if pos + 4 <= len(self.data):
                    args.append(struct.unpack('<i', self.data[pos:pos+4])[0])
            elif arg_type == 'literal':
                if pos + 2 <= len(self.data):
                    idx = struct.unpack('<H', self.data[pos:pos+2])[0]
                    args.append(f'lit[{idx}]')
                    # 尝试获取实际值
                    if idx < len(self.literals):
                        args[-1] += f'={repr(self.literals[idx].value)[:20]}'
            elif arg_type == 'literal_byte':
                if pos + 2 <= len(self.data):
                    idx = self.data[pos]
                    args.append(f'lit[{idx}]')
                    if idx < len(self.literals):
                        args[-1] += f'={repr(self.literals[idx].value)[:20]}'
                    args.append(self.data[pos+1])
            elif arg_type == 'branch':
                if pos + 1 <= len(self.data):
                    # 分支偏移是变长编码
                    size = self._get_branch_size(self.data[pos])
                    if pos + size <= len(self.data):
                        if size == 1:
                            offset = struct.unpack('<b', self.data[pos:pos+1])[0]
                        elif size == 2:
                            offset = struct.unpack('<h', self.data[pos:pos+2])[0]
                        else:
                            offset = struct.unpack('<i', self.data[pos:pos+4])[0]
                        args.append(f'offset={offset}')
            elif arg_type == 'double':
                if pos + 8 <= len(self.data):
                    args.append(struct.unpack('<d', self.data[pos:pos+8])[0])
            elif arg_type == 'float':
                if pos + 4 <= len(self.data):
                    args.append(struct.unpack('<f', self.data[pos:pos+4])[0])
            elif arg_type == 'byte_byte':
                if pos + 2 <= len(self.data):
                    args.append(self.data[pos])
                    args.append(self.data[pos+1])
        
        except Exception:
            pass
        
        return args
    
    def _get_argument_size(self, arg_type: str, pos: int) -> int:
        """获取参数大小"""
        if arg_type == 'no_args':
            return 0
        elif arg_type == 'byte':
            return 1
        elif arg_type == 'i8':
            return 1
        elif arg_type == 'i16':
            return 2
        elif arg_type == 'i32':
            return 4
        elif arg_type == 'literal':
            return 2
        elif arg_type == 'literal_byte':
            return 2
        elif arg_type == 'branch':
            if pos < len(self.data):
                return self._get_branch_size(self.data[pos])
            return 1
        elif arg_type == 'double':
            return 8
        elif arg_type == 'float':
            return 4
        elif arg_type == 'byte_byte':
            return 2
        return 1
    
    def _get_branch_size(self, first_byte: int) -> int:
        """获取分支偏移大小"""
        if first_byte & 0x80:
            return 1
        elif first_byte & 0x40:
            return 2
        else:
            return 4
    
    def _parse_functions(self):
        """解析函数结构"""
        functions = []
        current_func = None
        
        for instr in self.instructions:
            if instr.name == 'EXT_NEW_FUNCTION':
                # 开始新函数
                if current_func:
                    functions.append(current_func)
                
                func_name = 'anonymous'
                for arg in instr.args:
                    if 'lit[' in arg:
                        match = re.search(r'lit\[(\d+)\]', arg)
                        if match:
                            idx = int(match.group(1))
                            if idx < len(self.literals):
                                func_name = self.literals[idx].value
                
                current_func = {
                    'name': func_name,
                    'instructions': [],
                    'params': [],
                    'locals': 0
                }
            
            elif current_func:
                current_func['instructions'].append(instr)
                
                # 统计本地变量
                if 'STORE_LOCAL' in instr.name:
                    for arg in instr.args:
                        match = re.search(r'(\d+)', str(arg))
                        if match:
                            current_func['locals'] = max(current_func['locals'], int(match.group(1)) + 1)
                
                # 检测函数结束
                if instr.name.startswith('RETURN'):
                    functions.append(current_func)
                    current_func = None
        
        if current_func:
            functions.append(current_func)
        
        self.functions = functions
    
    def _generate_code(self) -> str:
        """生成反编译代码"""
        lines = []
        
        # 头部信息
        lines.append(f"// JerryScript CBC Bytecode Decompiler")
        lines.append(f"// File size: {len(self.data)} bytes")
        lines.append(f"// Magic: {self.header.magic.hex()}")
        lines.append(f"// Version: {self.header.version}")
        lines.append(f"// Stack limit: {self.header.stack_limit}")
        lines.append(f"// Arguments: {self.header.argument_end}")
        lines.append(f"// Registers: {self.header.register_end}")
        lines.append(f"// Literals: {len(self.literals)}")
        lines.append(f"// Instructions: {len(self.instructions)}")
        lines.append("")
        
        # 字面量池
        lines.append("// === Literal Pool ===")
        for lit in self.literals:
            if lit.type == CBCValueType.STRING:
                lines.append(f"// [{lit.index}] \"{lit.value}\"")
            elif lit.type == CBCValueType.NUMBER:
                lines.append(f"// [{lit.index}] {lit.value}")
            elif lit.type == CBCValueType.BOOLEAN:
                lines.append(f"// [{lit.index}] {str(lit.value).lower()}")
            else:
                lines.append(f"// [{lit.index}] {lit.type.name}: {lit.value}")
        lines.append("")
        
        # 函数定义
        if self.functions:
            lines.append("// === Functions ===")
            for func in self.functions:
                lines.append(f"function {func['name']}(")
                if func['params']:
                    lines.append(f"  {', '.join(func['params'])}")
                lines.append(") {")
                lines.append(f"  // locals: {func['locals']}")
                lines.append("")
                
                # 反编译函数体
                func_code = self._decompile_function(func['instructions'])
                lines.extend([f"  {line}" for line in func_code])
                
                lines.append("}")
                lines.append("")
        
        # 全局代码
        lines.append("// === Global Code ===")
        global_code = self._decompile_instructions(self.instructions)
        lines.extend(global_code)
        
        return '\n'.join(lines)
    
    def _decompile_function(self, instructions: List[CBCInstruction]) -> List[str]:
        """反编译单个函数"""
        lines = []
        stack = []
        indent = 0
        
        for instr in instructions:
            line = self._instruction_to_js(instr, stack)
            if line:
                # 处理缩进
                if instr.name in ['EXT_IF', 'EXT_IF_ELSE', 'EXT_WHILE', 'EXT_FOR', 
                                'EXT_FOR_IN', 'EXT_FOR_OF', 'EXT_DO_WHILE']:
                    lines.append('  ' * indent + line)
                    indent += 1
                elif instr.name == 'RETURN':
                    indent = max(0, indent - 1)
                    lines.append('  ' * indent + line)
                else:
                    lines.append('  ' * indent + line)
        
        return lines
    
    def _decompile_instructions(self, instructions: List[CBCInstruction]) -> List[str]:
        """反编译指令序列"""
        lines = []
        stack = []
        indent = 0
        pending_else = False
        
        for instr in instructions:
            line = self._instruction_to_js(instr, stack)
            if line:
                if pending_else and instr.name == 'EXT_IF':
                    lines.append('  ' * (indent - 1) + 'else {')
                    pending_else = False
                elif instr.name in ['EXT_IF_ELSE']:
                    lines.append('  ' * indent + line)
                    pending_else = True
                elif instr.name in ['EXT_IF', 'EXT_WHILE', 'EXT_FOR', 
                                'EXT_FOR_IN', 'EXT_FOR_OF', 'EXT_DO_WHILE']:
                    lines.append('  ' * indent + line)
                    indent += 1
                elif instr.name == 'RETURN':
                    lines.append('  ' * indent + line)
                else:
                    lines.append('  ' * indent + line)
        
        return lines
    
    def _instruction_to_js(self, instr: CBCInstruction, stack: List[str]) -> str:
        """将单条指令转换为JavaScript"""
        name = instr.name
        args = instr.args
        
        # 常量压栈
        if name.startswith('PUSH_LIT'):
            for arg in args:
                match = re.search(r'lit\[(\d+)\]', str(arg))
                if match:
                    idx = int(match.group(1))
                    if idx < len(self.literals):
                        val = self.literals[idx].value
                        if isinstance(val, str):
                            stack.append(f'"{val}"')
                        else:
                            stack.append(str(val))
            return None
        
        elif name == 'PUSH_TRUE':
            stack.append('true')
            return None
        elif name == 'PUSH_FALSE':
            stack.append('false')
            return None
        elif name == 'PUSH_NULL':
            stack.append('null')
            return None
        elif name == 'PUSH_UNDEFINED':
            stack.append('undefined')
            return None
        
        # 算术运算
        elif name == 'ADD' and len(stack) >= 2:
            b = stack.pop()
            a = stack.pop()
            stack.append(f"({a} + {b})")
            return None
        elif name == 'SUB' and len(stack) >= 2:
            b = stack.pop()
            a = stack.pop()
            stack.append(f"({a} - {b})")
            return None
        elif name == 'MUL' and len(stack) >= 2:
            b = stack.pop()
            a = stack.pop()
            stack.append(f"({a} * {b})")
            return None
        elif name == 'DIV' and len(stack) >= 2:
            b = stack.pop()
            a = stack.pop()
            stack.append(f"({a} / {b})")
            return None
        elif name == 'MOD' and len(stack) >= 2:
            b = stack.pop()
            a = stack.pop()
            stack.append(f"({a} % {b})")
            return None
        
        # 比较运算
        elif name == 'EQ' and len(stack) >= 2:
            b = stack.pop()
            a = stack.pop()
            stack.append(f"({a} == {b})")
            return None
        elif name == 'NE' and len(stack) >= 2:
            b = stack.pop()
            a = stack.pop()
            stack.append(f"({a} != {b})")
            return None
        elif name == 'STRICT_EQ' and len(stack) >= 2:
            b = stack.pop()
            a = stack.pop()
            stack.append(f"({a} === {b})")
            return None
        elif name == 'STRICT_NE' and len(stack) >= 2:
            b = stack.pop()
            a = stack.pop()
            stack.append(f"({a} !== {b})")
            return None
        
        # 函数调用
        elif name.startswith('CALL'):
            arg_count = 0
            for arg in args:
                if isinstance(arg, int):
                    arg_count = arg
                    break
            
            call_args = []
            for _ in range(arg_count):
                if stack:
                    call_args.insert(0, stack.pop())
            
            if stack:
                func_name = stack.pop()
                return f"{func_name}({', '.join(call_args)});"
        
        # 返回指令
        elif name == 'RETURN':
            if stack:
                return f"return {stack.pop()};"
            return "return;"
        elif name == 'RETURN_UNDEFINED':
            return "return undefined;"
        elif name == 'RETURN_NULL':
            return "return null;"
        elif name == 'RETURN_TRUE':
            return "return true;"
        elif name == 'RETURN_FALSE':
            return "return false;"
        
        # 控制流
        elif name == 'EXT_IF':
            if stack:
                cond = stack.pop()
                return f"if ({cond}) {{"
            return "if (/* condition */) {"
        elif name == 'EXT_IF_ELSE':
            return "} else {"
        elif name == 'EXT_WHILE':
            if stack:
                cond = stack.pop()
                return f"while ({cond}) {{"
            return "while (/* condition */) {"
        elif name == 'EXT_FOR':
            return "for (/* init */; /* condition */; /* increment */) {"
        
        # 对象/数组操作
        elif name == 'NEW_OBJECT':
            stack.append('{}')
            return None
        elif name == 'NEW_ARRAY':
            stack.append('[]')
            return None
        
        # 属性访问
        elif name == 'GET_BY_STR_LIT':
            if len(stack) >= 2:
                prop = args[0] if args else '""'
                obj = stack.pop()
                stack.append(f"{obj}[{prop}]")
            return None
        elif name == 'SET_BY_STR_LIT':
            if len(stack) >= 2:
                val = stack.pop()
                prop = args[0] if args else '""'
                obj = stack.pop()
                return f"{obj}[{prop}] = {val};"
        
        # 变量存储
        elif name.startswith('STORE_LOCAL'):
            if stack:
                val = stack.pop()
                idx = args[0] if args else 0
                return f"var v{idx} = {val};"
        
        # 内置函数调用
        elif name.startswith('EXT_CALL_BUILTIN'):
            builtin_id = args[0] if args else 0
            builtin_names = {
                0: 'parseInt', 1: 'parseFloat', 2: 'isNaN', 3: 'isFinite',
                4: 'encodeURI', 5: 'decodeURI', 6: 'encodeURIComponent',
                7: 'decodeURIComponent', 8: 'eval', 9: 'typeof',
                10: 'instanceof', 11: 'delete', 12: 'void', 13: 'throw'
            }
            func_name = builtin_names.get(builtin_id, f'builtin_{builtin_id}')
            arg_count = int(name.split('_')[-1]) if '_' in name else 0
            
            call_args = []
            for _ in range(arg_count):
                if stack:
                    call_args.insert(0, stack.pop())
            
            result = f"{func_name}({', '.join(call_args)});"
            stack.append(f"/* result */")
            return result
        
        # 默认：输出原始指令
        args_str = ', '.join(str(a) for a in args)
        return f"// {name} {args_str}"


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.jsc> <output.js>")
        sys.exit(1)
    
    decompiler = JerryScriptDecompiler()
    result = decompiler.decompile(sys.argv[1])
    
    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        f.write(result)
    
    print(f"Decompilation complete. Output written to {sys.argv[2]}")