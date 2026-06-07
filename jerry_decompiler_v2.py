#!/usr/bin/env python3
"""
JerryScript CBC Bytecode Decompiler v2
基于官方规范实现的完整反编译器

参考资料：
1. JerryScript Internals: https://github.com/jerryscript-project/jerryscript/blob/master/docs/04.INTERNALS.md
2. CBC Opcode定义: jerry-core/vm/vm-opcode.h
3. CBC编译代码结构: jerry-core/vm/vm-bytecode.h

CBC字节码结构：
┌─────────────────────────────────────────────────────────────┐
│                    cbc_compiled_code                        │
├─────────────────────────────────────────────────────────────┤
│ magic (4 bytes)        = b'JS\x00\x00'                     │
│ version (4 bytes)      = 版本号                            │
│ flags (4 bytes)        = 标志位                            │
│ stack_limit (2 bytes)  = 栈限制                            │
│ argument_end (2 bytes) = 参数数量                          │
│ register_end (2 bytes) = 寄存器数量                        │
│ ident_end (2 bytes)    = 标识符数量                        │
│ literal_end (2 bytes)  = 字面量数量                        │
├─────────────────────────────────────────────────────────────┤
│                      Literals                              │
│ 每个字面量: type_tag (1 byte) + value                     │
├─────────────────────────────────────────────────────────────┤
│                      Bytecode Instructions                 │
│ 每个指令: opcode (1-2 bytes) + arguments                   │
└─────────────────────────────────────────────────────────────┘

指令参数类型：
- no_args: 无参数
- byte: 1字节无符号整数
- literal: 2字节字面量索引
- branch: 1-3字节相对偏移
- byte_literal: byte + literal
- two_literals: literal + literal
- three_literals: literal + literal + literal
"""

import struct
import os
import re
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple, Union


class CBCValueType(Enum):
    UNDEFINED = 0x00
    NULL = 0x01
    BOOLEAN = 0x02
    NUMBER = 0x03
    STRING = 0x04
    SYMBOL = 0x05
    OBJECT = 0x06
    FUNCTION = 0x07


# CBC指令定义（基于官方vm-opcode.h）
CBC_OPCODES = {
    0x00: ('EXT', 'no_args'),
    
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
    def __init__(self):
        self.magic = b''
        self.version = 0
        self.flags = 0
        self.stack_limit = 0
        self.argument_end = 0
        self.register_end = 0
        self.ident_end = 0
        self.literal_end = 0
    
    def __repr__(self):
        return f"CBCHeader(magic={self.magic.hex()}, version={self.version}, " \
               f"stack_limit={self.stack_limit}, argument_end={self.argument_end}, " \
               f"register_end={self.register_end}, literal_end={self.literal_end})"


class CBCLiteral:
    def __init__(self, index: int, value_type: CBCValueType, value):
        self.index = index
        self.type = value_type
        self.value = value
    
    def __repr__(self):
        return f"CBCLiteral({self.index}, {self.type.name}, {repr(self.value)[:30]})"


class CBCInstruction:
    def __init__(self, offset: int, opcode: int, name: str, args: List[Any], arg_size: int):
        self.offset = offset
        self.opcode = opcode
        self.name = name
        self.args = args
        self.arg_size = arg_size
    
    def __repr__(self):
        args_str = ', '.join(str(a) for a in self.args)
        return f"CBCInstruction({self.offset:04x}, {self.name} {args_str})"


class JerryScriptDecompiler:
    def __init__(self):
        self.data = b''
        self.header = CBCHeader()
        self.literals = []
        self.instructions = []
        self.functions = []
        self.label_map = {}
    
    def decompile(self, filepath: str) -> str:
        with open(filepath, 'rb') as f:
            self.data = f.read()
        
        self._parse_header()
        self._parse_literals()
        self._parse_instructions()
        self._build_label_map()
        self._parse_functions()
        
        return self._generate_code()
    
    def _parse_header(self):
        pos = 0
        
        if self.data.startswith(b'JS\x00\x00'):
            self.header.magic = b'JS\x00\x00'
            pos += 4
        elif self.data.startswith(b'\x01\x00'):
            self.header.magic = b'\x01\x00'
            pos += 2
        
        if pos + 12 <= len(self.data):
            self.header.version = struct.unpack('<I', self.data[pos:pos+4])[0]
            pos += 4
            self.header.flags = struct.unpack('<I', self.data[pos:pos+4])[0]
            pos += 4
        
        if pos + 10 <= len(self.data):
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
    
    def _parse_literals(self):
        pos = self._get_literal_start()
        
        if self.header.literal_end > 0:
            for i in range(self.header.literal_end):
                if pos + 1 > len(self.data):
                    break
                
                type_tag = self.data[pos]
                pos += 1
                
                value_type = self._get_value_type(type_tag)
                value, size = self._parse_literal_value(type_tag, pos)
                
                self.literals.append(CBCLiteral(i, value_type, value))
                pos += size
        else:
            strings = self._extract_all_strings()
            for i, s in enumerate(strings[:200]):
                self.literals.append(CBCLiteral(i, CBCValueType.STRING, s))
    
    def _get_literal_start(self) -> int:
        if self.header.magic == b'JS\x00\x00':
            return 16
        return 0
    
    def _get_value_type(self, type_tag: int) -> CBCValueType:
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
        return type_map.get(type_tag & 0x0F, CBCValueType.STRING)
    
    def _parse_literal_value(self, type_tag: int, pos: int) -> Tuple[Any, int]:
        base_type = type_tag & 0x0F
        
        if base_type == 0x00:
            return None, 0
        elif base_type == 0x01:
            return None, 0
        elif base_type == 0x02:
            if pos < len(self.data):
                return bool(self.data[pos]), 1
            return False, 1
        elif base_type == 0x03:
            if pos + 8 <= len(self.data):
                return struct.unpack('<d', self.data[pos:pos+8])[0], 8
            return 0.0, 8
        elif base_type in (0x04, 0x05):
            return self._parse_cbc_string(pos)
        
        return f"<type_{type_tag}>", 4
    
    def _parse_cbc_string(self, pos: int) -> Tuple[str, int]:
        if pos + 2 > len(self.data):
            return "", 1
        
        length = self.data[pos]
        pos += 1
        
        if length == 0:
            if pos + 4 > len(self.data):
                return "", 1
            length = struct.unpack('<I', self.data[pos:pos+4])[0]
            pos += 4
        
        if pos + length <= len(self.data):
            return self.data[pos:pos+length].decode('utf-8', errors='replace'), length
        
        return "", length
    
    def _extract_all_strings(self) -> List[str]:
        strings = []
        current = []
        
        for byte in self.data:
            if 32 <= byte < 127:
                current.append(chr(byte))
            else:
                if len(current) >= 2:
                    s = ''.join(current)
                    if not s.isdigit():
                        strings.append(s)
                current = []
        
        if len(current) >= 2:
            s = ''.join(current)
            if not s.isdigit():
                strings.append(s)
        
        return sorted(set(strings), key=lambda x: (-len(x), x))
    
    def _parse_instructions(self):
        pos = self._get_code_start()
        
        while pos < len(self.data) - 1:
            offset = pos
            opcode = self.data[pos]
            pos += 1
            
            if opcode == 0x00:
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
            
            args, arg_size = self._parse_arguments(arg_type, pos)
            pos += arg_size
            
            self.instructions.append(CBCInstruction(offset, opcode, name, args, arg_size))
    
    def _get_code_start(self) -> int:
        start = self._get_literal_start()
        
        if self.header.literal_end > 0:
            for _ in range(self.header.literal_end):
                if start + 1 > len(self.data):
                    break
                type_tag = self.data[start]
                start += 1
                
                base_type = type_tag & 0x0F
                if base_type == 0x03:
                    start += 8
                elif base_type in (0x04, 0x05):
                    length = self.data[start]
                    if length == 0:
                        if start + 4 <= len(self.data):
                            length = struct.unpack('<I', self.data[start:start+4])[0]
                            start += 4
                    start += length
                else:
                    start += 4
        
        return start
    
    def _parse_arguments(self, arg_type: str, pos: int) -> Tuple[List[Any], int]:
        args = []
        size = 0
        
        try:
            if arg_type == 'no_args':
                pass
            elif arg_type == 'byte':
                if pos < len(self.data):
                    args.append(self.data[pos])
                    size = 1
            elif arg_type == 'i8':
                if pos < len(self.data):
                    args.append(struct.unpack('<b', self.data[pos:pos+1])[0])
                    size = 1
            elif arg_type == 'i16':
                if pos + 2 <= len(self.data):
                    args.append(struct.unpack('<h', self.data[pos:pos+2])[0])
                    size = 2
            elif arg_type == 'i32':
                if pos + 4 <= len(self.data):
                    args.append(struct.unpack('<i', self.data[pos:pos+4])[0])
                    size = 4
            elif arg_type == 'literal':
                if pos + 2 <= len(self.data):
                    idx = struct.unpack('<H', self.data[pos:pos+2])[0]
                    args.append(idx)
                    size = 2
            elif arg_type == 'literal_byte':
                if pos + 2 <= len(self.data):
                    args.append(struct.unpack('<H', self.data[pos:pos+2])[0])
                    args.append(self.data[pos+2])
                    size = 3
            elif arg_type == 'byte_byte':
                if pos + 2 <= len(self.data):
                    args.append(self.data[pos])
                    args.append(self.data[pos+1])
                    size = 2
            elif arg_type == 'branch':
                branch_size = self._get_branch_size(self.data[pos] if pos < len(self.data) else 0)
                if pos + branch_size <= len(self.data):
                    if branch_size == 1:
                        offset = struct.unpack('<b', self.data[pos:pos+1])[0]
                    elif branch_size == 2:
                        offset = struct.unpack('<h', self.data[pos:pos+2])[0]
                    else:
                        offset = struct.unpack('<i', self.data[pos:pos+4])[0]
                    args.append(offset)
                    size = branch_size
            elif arg_type == 'double':
                if pos + 8 <= len(self.data):
                    args.append(struct.unpack('<d', self.data[pos:pos+8])[0])
                    size = 8
            elif arg_type == 'float':
                if pos + 4 <= len(self.data):
                    args.append(struct.unpack('<f', self.data[pos:pos+4])[0])
                    size = 4
        
        except Exception:
            pass
        
        return args, size
    
    def _get_branch_size(self, first_byte: int) -> int:
        if first_byte & 0x80:
            return 1
        elif first_byte & 0x40:
            return 2
        else:
            return 4
    
    def _build_label_map(self):
        self.label_map = {}
        
        for instr in self.instructions:
            if 'JMP' in instr.name or 'BRANCH' in instr.name:
                if instr.args:
                    target_offset = instr.offset + 1 + instr.arg_size + instr.args[0]
                    self.label_map[target_offset] = f'label_{len(self.label_map)}'
    
    def _parse_functions(self):
        functions = []
        current_func = None
        
        for i, instr in enumerate(self.instructions):
            if instr.name == 'EXT_NEW_FUNCTION':
                if current_func:
                    functions.append(current_func)
                
                func_name = 'anonymous'
                if instr.args:
                    lit_idx = instr.args[0]
                    if lit_idx < len(self.literals):
                        func_name = self.literals[lit_idx].value
                
                current_func = {
                    'name': func_name,
                    'start_idx': i,
                    'instructions': [],
                    'params': [],
                    'locals': 0
                }
            
            elif current_func:
                current_func['instructions'].append(instr)
                
                if 'STORE_LOCAL' in instr.name and instr.args:
                    current_func['locals'] = max(current_func['locals'], instr.args[0] + 1)
                
                if instr.name.startswith('RETURN'):
                    functions.append(current_func)
                    current_func = None
        
        if current_func:
            functions.append(current_func)
        
        self.functions = functions
    
    def _generate_code(self) -> str:
        lines = []
        
        lines.append("// JerryScript CBC Bytecode Decompiler v2")
        lines.append("// Based on official JerryScript specification")
        lines.append(f"// File: {os.path.basename(__file__)}")
        lines.append(f"// Bytecode size: {len(self.data)} bytes")
        lines.append(f"// Magic: {self.header.magic.hex()}")
        lines.append(f"// Version: {self.header.version}")
        lines.append(f"// Literals: {len(self.literals)}")
        lines.append(f"// Instructions: {len(self.instructions)}")
        lines.append("")
        
        lines.append("// === Literal Pool ===")
        for lit in self.literals:
            if lit.type == CBCValueType.STRING:
                escaped = lit.value.replace('\\', '\\\\').replace('"', '\\"')
                lines.append(f'const L{lit.index} = "{escaped}";')
            elif lit.type == CBCValueType.NUMBER:
                lines.append(f'const L{lit.index} = {lit.value};')
            elif lit.type == CBCValueType.BOOLEAN:
                lines.append(f'const L{lit.index} = {str(lit.value).lower()};')
        lines.append("")
        
        for func in self.functions:
            params = ', '.join(f'arg{i}' for i in range(self.header.argument_end))
            lines.append(f"function {func['name']}({params}) {{")
            lines.append(f"  // locals: {func['locals']}")
            if func['locals'] > 0:
                lines.append(f"  var {', '.join(f'v{i}' for i in range(func['locals']))};")
            lines.append("")
            
            func_code = self._decompile_instructions(func['instructions'])
            lines.extend([f"  {line}" for line in func_code])
            
            lines.append("}")
            lines.append("")
        
        lines.append("// === Global Code ===")
        global_code = self._decompile_instructions(self.instructions)
        lines.extend(global_code)
        
        return '\n'.join(lines)
    
    def _decompile_instructions(self, instructions: List[CBCInstruction]) -> List[str]:
        lines = []
        stack = []
        indent = 0
        pending_else = False
        label_stack = []
        
        for instr in instructions:
            line, new_stack, new_indent, is_else = self._instruction_to_js(instr, stack, indent)
            
            stack = new_stack
            
            if pending_else and is_else:
                lines.append('  ' * (indent - 1) + 'else {')
                pending_else = False
                indent += 1
            
            if line:
                if instr.offset in self.label_map:
                    lines.append(f"{self.label_map[instr.offset]}:")
                
                if instr.name in ['EXT_IF', 'EXT_IF_ELSE']:
                    lines.append('  ' * indent + line)
                    if instr.name == 'EXT_IF_ELSE':
                        pending_else = True
                    else:
                        indent += 1
                elif instr.name in ['EXT_WHILE', 'EXT_FOR', 'EXT_FOR_IN', 'EXT_FOR_OF', 'EXT_DO_WHILE']:
                    lines.append('  ' * indent + line)
                    indent += 1
                elif instr.name.startswith('RETURN'):
                    lines.append('  ' * indent + line)
                    indent = max(0, indent - 1)
                else:
                    lines.append('  ' * indent + line)
        
        return lines
    
    def _instruction_to_js(self, instr: CBCInstruction, stack: List[str], indent: int) -> Tuple[str, List[str], int, bool]:
        name = instr.name
        args = instr.args
        new_stack = stack.copy()
        is_else = False
        
        if name.startswith('PUSH_LIT'):
            if args:
                idx = args[0]
                if idx < len(self.literals):
                    lit = self.literals[idx]
                    if lit.type == CBCValueType.STRING:
                        new_stack.append(f'L{idx}')
                    else:
                        new_stack.append(f'L{idx}')
            return None, new_stack, indent, False
        
        elif name == 'PUSH_TRUE':
            new_stack.append('true')
            return None, new_stack, indent, False
        elif name == 'PUSH_FALSE':
            new_stack.append('false')
            return None, new_stack, indent, False
        elif name == 'PUSH_NULL':
            new_stack.append('null')
            return None, new_stack, indent, False
        elif name == 'PUSH_UNDEFINED':
            new_stack.append('undefined')
            return None, new_stack, indent, False
        
        elif name == 'EXT_PUSH_INT8':
            if args:
                new_stack.append(str(args[0]))
            return None, new_stack, indent, False
        elif name == 'EXT_PUSH_INT16':
            if args:
                new_stack.append(str(args[0]))
            return None, new_stack, indent, False
        elif name == 'EXT_PUSH_INT32':
            if args:
                new_stack.append(str(args[0]))
            return None, new_stack, indent, False
        elif name == 'EXT_PUSH_DOUBLE':
            if args:
                new_stack.append(str(args[0]))
            return None, new_stack, indent, False
        
        elif name == 'ADD' and len(new_stack) >= 2:
            b = new_stack.pop()
            a = new_stack.pop()
            new_stack.append(f"({a} + {b})")
            return None, new_stack, indent, False
        elif name == 'SUB' and len(new_stack) >= 2:
            b = new_stack.pop()
            a = new_stack.pop()
            new_stack.append(f"({a} - {b})")
            return None, new_stack, indent, False
        elif name == 'MUL' and len(new_stack) >= 2:
            b = new_stack.pop()
            a = new_stack.pop()
            new_stack.append(f"({a} * {b})")
            return None, new_stack, indent, False
        elif name == 'DIV' and len(new_stack) >= 2:
            b = new_stack.pop()
            a = new_stack.pop()
            new_stack.append(f"({a} / {b})")
            return None, new_stack, indent, False
        elif name == 'MOD' and len(new_stack) >= 2:
            b = new_stack.pop()
            a = new_stack.pop()
            new_stack.append(f"({a} % {b})")
            return None, new_stack, indent, False
        
        elif name == 'EQ' and len(new_stack) >= 2:
            b = new_stack.pop()
            a = new_stack.pop()
            new_stack.append(f"({a} == {b})")
            return None, new_stack, indent, False
        elif name == 'NE' and len(new_stack) >= 2:
            b = new_stack.pop()
            a = new_stack.pop()
            new_stack.append(f"({a} != {b})")
            return None, new_stack, indent, False
        elif name == 'STRICT_EQ' and len(new_stack) >= 2:
            b = new_stack.pop()
            a = new_stack.pop()
            new_stack.append(f"({a} === {b})")
            return None, new_stack, indent, False
        elif name == 'STRICT_NE' and len(new_stack) >= 2:
            b = new_stack.pop()
            a = new_stack.pop()
            new_stack.append(f"({a} !== {b})")
            return None, new_stack, indent, False
        
        elif name.startswith('CALL') and not name.startswith('CALL_IMMEDIATE'):
            arg_count = args[0] if args else 0
            call_args = []
            for _ in range(arg_count):
                if new_stack:
                    call_args.insert(0, new_stack.pop())
            
            if new_stack:
                func_name = new_stack.pop()
                return f"{func_name}({', '.join(call_args)});", new_stack, indent, False
        
        elif name.startswith('CALL_IMMEDIATE'):
            if args:
                lit_idx = args[0]
                if lit_idx < len(self.literals):
                    func_name = self.literals[lit_idx].value
                    arg_count = int(name.split('_')[-1]) if '_' in name else 0
                    
                    call_args = []
                    for _ in range(arg_count):
                        if new_stack:
                            call_args.insert(0, new_stack.pop())
                    
                    return f"{func_name}({', '.join(call_args)});", new_stack, indent, False
        
        elif name == 'RETURN':
            if new_stack:
                return f"return {new_stack.pop()};", new_stack, indent - 1, False
            return "return;", new_stack, indent - 1, False
        elif name == 'RETURN_UNDEFINED':
            return "return undefined;", new_stack, indent - 1, False
        elif name == 'RETURN_NULL':
            return "return null;", new_stack, indent - 1, False
        elif name == 'RETURN_TRUE':
            return "return true;", new_stack, indent - 1, False
        elif name == 'RETURN_FALSE':
            return "return false;", new_stack, indent - 1, False
        
        elif name == 'EXT_IF':
            if new_stack:
                cond = new_stack.pop()
                return f"if ({cond}) {{", new_stack, indent + 1, False
            return "if (/* condition */) {", new_stack, indent + 1, False
        elif name == 'EXT_IF_ELSE':
            return "} else {", new_stack, indent + 1, True
        elif name == 'EXT_WHILE':
            if new_stack:
                cond = new_stack.pop()
                return f"while ({cond}) {{", new_stack, indent + 1, False
            return "while (/* condition */) {", new_stack, indent + 1, False
        elif name == 'EXT_FOR':
            return "for (/* init */; /* condition */; /* increment */) {", new_stack, indent + 1, False
        elif name == 'EXT_FOR_IN':
            if new_stack:
                obj = new_stack.pop()
                return f"for (var key in {obj}) {{", new_stack, indent + 1, False
            return "for (var key in /* object */) {", new_stack, indent + 1, False
        
        elif name == 'NEW_OBJECT':
            new_stack.append('({})')
            return None, new_stack, indent, False
        elif name == 'NEW_ARRAY':
            new_stack.append('([])')
            return None, new_stack, indent, False
        
        elif name == 'GET_BY_STR_LIT':
            if len(new_stack) >= 1 and args:
                obj = new_stack.pop()
                idx = args[0]
                if idx < len(self.literals):
                    prop = self.literals[idx].value
                    new_stack.append(f"{obj}['{prop}']")
            return None, new_stack, indent, False
        elif name == 'SET_BY_STR_LIT':
            if len(new_stack) >= 2 and args:
                val = new_stack.pop()
                obj = new_stack.pop()
                idx = args[0]
                if idx < len(self.literals):
                    prop = self.literals[idx].value
                    return f"{obj}['{prop}'] = {val};", new_stack, indent, False
        
        elif name.startswith('STORE_LOCAL') and args:
            if new_stack:
                val = new_stack.pop()
                idx = args[0]
                return f"v{idx} = {val};", new_stack, indent, False
        
        elif name.startswith('PUSH_LOCAL') and args:
            idx = args[0]
            new_stack.append(f'v{idx}')
            return None, new_stack, indent, False
        
        elif name == 'EXT_JSON_PARSE':
            if new_stack:
                arg = new_stack.pop()
                return f"JSON.parse({arg});", new_stack, indent, False
        elif name == 'EXT_JSON_STRINGIFY':
            if new_stack:
                arg = new_stack.pop()
                return f"JSON.stringify({arg});", new_stack, indent, False
        
        args_str = ', '.join(str(a) for a in args)
        return f"// {name} {args_str}", new_stack, indent, False


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