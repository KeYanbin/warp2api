#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志工具模块
统一的日志管理，基于loguru
"""

import sys
from loguru import logger as _logger
from config import config


class Logger:
    """日志管理器"""
    
    def __init__(self):
        # 移除默认处理器
        _logger.remove()
        
        # 添加控制台输出
        _logger.add(
            sys.stdout,
            level=config.LOG_LEVEL,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                   "<level>{message}</level>",
            colorize=True
        )
        
        # 添加文件输出
        _logger.add(
            config.LOG_FILE,
            level=config.LOG_LEVEL,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="100 MB",
            retention="7 days",
            compression="zip"
        )
    
    def info(self, message: str):
        """信息日志"""
        _logger.info(message)
    
    def debug(self, message: str):
        """调试日志"""
        _logger.debug(message)
    
    def warning(self, message: str):
        """警告日志"""
        _logger.warning(message)
    
    def error(self, message: str):
        """错误日志"""
        _logger.error(message)
    
    def critical(self, message: str):
        """严重错误日志"""
        _logger.critical(message)
    
    def success(self, message: str):
        """成功日志"""
        _logger.success(message)


# 全局日志实例
logger = Logger()