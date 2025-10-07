#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立账号池服务
提供RESTful API供其他服务调用，支持多进程并发
"""

import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.responses import JSONResponse
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

from config import config
from utils.logger import logger
from account_pool.pool_manager import get_pool_manager
from account_pool.database import Account
from account_pool.moemail_client import MoeMailClient
from account_pool.quota_tracker import get_quota_tracker

# 请求响应模型
class AllocateAccountRequest(BaseModel):
    """分配账号请求"""
    session_id: Optional[str] = Field(None, description="会话ID，如果不提供会自动生成")
    count: Optional[int] = Field(1, description="需要分配的账号数量", ge=1, le=10)

class ReleaseAccountRequest(BaseModel):
    """释放账号请求"""
    session_id: str = Field(..., description="要释放的会话ID")

class RefreshTokenRequest(BaseModel):
    """刷新Token请求"""
    email: Optional[str] = Field(None, description="指定账号邮箱")
    force: Optional[bool] = Field(False, description="是否强制刷新（忽略时间限制）")

class ManualReplenishRequest(BaseModel):
    """手动补充账号请求"""
    count: Optional[int] = Field(None, description="补充数量，默认使用配置值")

class CreateUserRequest(BaseModel):
    """创建邮箱用户请求"""
    email: str = Field(..., description="邮箱地址")
    password: Optional[str] = Field(None, description="密码，不填自动生成")
    roleName: Optional[str] = Field(None, description="权限身份，不填自动分配默认身份")

class CreateUsersRequest(BaseModel):
    """批量创建邮箱用户请求"""
    list: List[CreateUserRequest] = Field(..., description="用户列表")

class CreateUsersResponse(BaseModel):
    """创建用户响应"""
    code: int
    message: str
    data: Optional[Any] = None

class EmailListRequest(BaseModel):
    """邮件列表请求"""
    num: int = Field(1, description="页码")
    size: int = Field(10, description="页大小")
    sendEmail: Optional[str] = Field(None, description="发送者邮箱")
    sendName: Optional[str] = Field(None, description="发送者姓名")
    toEmail: str = Field(..., description="接收者邮箱")

class EmailListResponse(BaseModel):
    """邮件列表响应"""
    code: int
    message: str
    data: Optional[List[Dict[str, Any]]] = None

class AccountInfo(BaseModel):
    """账号信息响应"""
    email: str
    local_id: str  # Warp UID
    id_token: str
    refresh_token: str
    status: str
    created_at: Optional[str]
    last_used: Optional[str]
    last_refresh_time: Optional[str]
    use_count: int
    session_id: Optional[str]

class AllocateAccountResponse(BaseModel):
    """分配账号响应"""
    success: bool
    session_id: str
    accounts: List[AccountInfo]
    message: Optional[str] = None

class PoolStatusResponse(BaseModel):
    """账号池状态响应"""
    pool_stats: Dict[str, int]
    active_sessions: int
    running: bool
    min_pool_size: int
    accounts_per_request: int
    health: str
    timestamp: str

# 全局账号池管理器
pool_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global pool_manager
    
    # 启动时初始化
    logger.info("🚀 启动账号池服务...")
    
    try:
        pool_manager = get_pool_manager()
        await pool_manager.start()
        logger.success("✅ 账号池服务启动完成")
    except Exception as e:
        logger.error(f"❌ 服务启动失败: {e}")
        raise
    
    yield
    
    # 关闭时清理
    logger.info("🛑 关闭账号池服务...")
    try:
        if pool_manager:
            await pool_manager.stop()
        logger.info("✅ 账号池服务已关闭")
    except Exception as e:
        logger.error(f"❌ 服务关闭时出错: {e}")

# 创建FastAPI应用
app = FastAPI(
    title="账号池服务",
    description="独立的Warp账号池管理服务，提供RESTful API接口",
    version="1.0.0",
    lifespan=lifespan
)

# API路由

@app.get("/health")
async def health_check():
    """健康检查"""
    if not pool_manager or not pool_manager._running:
        raise HTTPException(status_code=503, detail="服务不可用")
    
    status = await pool_manager.get_pool_status()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "pool_health": status["health"]
    }

@app.post("/api/accounts/allocate", response_model=AllocateAccountResponse)
async def allocate_accounts(request: AllocateAccountRequest):
    """分配账号给请求"""
    if not pool_manager or not pool_manager._running:
        raise HTTPException(status_code=503, detail="服务不可用")
    
    try:
        # 分配账号
        accounts = await pool_manager.allocate_accounts_for_request(
            request_id=request.session_id
        )
        
        if not accounts:
            return AllocateAccountResponse(
                success=False,
                session_id=request.session_id or "",
                accounts=[],
                message="无法分配账号，账号池可能不足"
            )
        
        # 转换为响应格式
        account_list = []
        for acc in accounts:
            account_list.append(AccountInfo(
                email=acc.email,
                local_id=acc.local_id,
                id_token=acc.id_token,
                refresh_token=acc.refresh_token,
                status=acc.status,
                created_at=acc.created_at.isoformat() if acc.created_at else None,
                last_used=acc.last_used.isoformat() if acc.last_used else None,
                last_refresh_time=acc.last_refresh_time.isoformat() if acc.last_refresh_time else None,
                use_count=acc.use_count,
                session_id=acc.session_id
            ))
        
        # 获取实际的session_id（可能是自动生成的）
        actual_session_id = accounts[0].session_id if accounts else request.session_id
        
        return AllocateAccountResponse(
            success=True,
            session_id=actual_session_id,
            accounts=account_list,
            message=f"成功分配 {len(accounts)} 个账号"
        )
        
    except Exception as e:
        logger.error(f"分配账号失败: {e}")
        raise HTTPException(status_code=500, detail=f"分配账号失败: {str(e)}")

@app.post("/api/accounts/mark_quota_exhausted")
async def mark_quota_exhausted(request: Dict[str, str]):
    """标记账号配额用尽"""
    email = request.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="缺少email参数")
    
    try:
        quota_tracker = get_quota_tracker()
        success = quota_tracker.mark_account_quota_exhausted(email)
        
        if success:
            return {
                "success": True,
                "message": f"成功标记账号 {email} 配额用尽"
            }
        else:
            return {
                "success": False,
                "message": f"标记账号 {email} 失败"
            }
    except Exception as e:
        logger.error(f"标记配额用尽失败: {e}")
        raise HTTPException(status_code=500, detail=f"标记失败: {str(e)}")

@app.get("/api/accounts/quota_status")
async def get_quota_status(email: str = Query(..., description="账号邮箱")):
    """获取账号的配额状态"""
    try:
        quota_tracker = get_quota_tracker()
        status = quota_tracker.get_quota_status(email)
        return status
    except Exception as e:
        logger.error(f"获取配额状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")

@app.get("/api/accounts/quota_exhausted")
async def get_exhausted_accounts():
    """获取所有配额用尽的账号"""
    try:
        quota_tracker = get_quota_tracker()
        accounts = quota_tracker.get_exhausted_accounts()
        return {
            "success": True,
            "count": len(accounts),
            "accounts": accounts
        }
    except Exception as e:
        logger.error(f"获取配额用尽账号列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取列表失败: {str(e)}")

@app.post("/api/accounts/release")
async def release_accounts(request: ReleaseAccountRequest):
    """释放会话的账号"""
    if not pool_manager or not pool_manager._running:
        raise HTTPException(status_code=503, detail="服务不可用")
    
    try:
        success = await pool_manager.release_accounts_for_request(request.session_id)
        
        if success:
            return {
                "success": True,
                "message": f"成功释放会话 {request.session_id} 的账号"
            }
        else:
            return {
                "success": False,
                "message": f"释放会话 {request.session_id} 失败"
            }
            
    except Exception as e:
        logger.error(f"释放账号失败: {e}")
        raise HTTPException(status_code=500, detail=f"释放账号失败: {str(e)}")

@app.get("/api/accounts/status", response_model=PoolStatusResponse)
async def get_pool_status():
    """获取账号池状态"""
    if not pool_manager:
        raise HTTPException(status_code=503, detail="服务不可用")
    
    try:
        status = await pool_manager.get_pool_status()
        
        return PoolStatusResponse(
            pool_stats=status["pool_stats"],
            active_sessions=status["active_sessions"],
            running=status["running"],
            min_pool_size=status["min_pool_size"],
            accounts_per_request=status["accounts_per_request"],
            health=status["health"],
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"获取状态失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取状态失败: {str(e)}")

@app.post("/api/accounts/refresh-tokens")
async def refresh_tokens(request: RefreshTokenRequest):
    """刷新账号Token"""
    if not pool_manager or not pool_manager._running:
        raise HTTPException(status_code=503, detail="服务不可用")
    
    try:
        result = await pool_manager.refresh_account_tokens_manually(
            email=request.email,
            force=request.force
        )
        
        return {
            "success": result["success_count"] > 0,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"刷新Token失败: {e}")
        raise HTTPException(status_code=500, detail=f"刷新Token失败: {str(e)}")

@app.post("/api/accounts/replenish")
async def manual_replenish(request: ManualReplenishRequest):
    """手动补充账号"""
    if not pool_manager or not pool_manager._running:
        raise HTTPException(status_code=503, detail="服务不可用")
    
    try:
        available_count = await pool_manager.manual_replenish(request.count)
        
        return {
            "success": True,
            "message": f"补充操作完成",
            "available_count": available_count
        }
        
    except Exception as e:
        logger.error(f"补充账号失败: {e}")
        raise HTTPException(status_code=500, detail=f"补充账号失败: {str(e)}")

@app.post("/api/pool/refresh")
async def refresh_pool():
    """刷新整个账号池"""
    if not pool_manager or not pool_manager._running:
        raise HTTPException(status_code=503, detail="服务不可用")
    
    try:
        success = await pool_manager.refresh_pool()
        
        return {
            "success": success,
            "message": "账号池刷新完成" if success else "账号池刷新失败"
        }
        
    except Exception as e:
        logger.error(f"刷新账号池失败: {e}")
        raise HTTPException(status_code=500, detail=f"刷新账号池失败: {str(e)}")

@app.post("/api/public/addUser", response_model=CreateUsersResponse)
async def create_email_users(request: CreateUsersRequest):
    """创建邮箱用户接口（新的API接口）"""
    # 使用配置中的API密钥，不再需要用户提供Authorization头
    
    try:
        # 使用主配置中的MoeMail设置
        # 创建 moemail客户端
        client = MoeMailClient(
            base_url=config.MOEMAIL_URL,
            api_key=config.MOEMAIL_API_KEY
        )
        
        # 处理用户列表
        created_users = []
        failed_users = []
        
        for user_request in request.list:
            try:
                # 使用新的addUser接口创建用户
                user_data = {
                    "email": user_request.email
                }
                if user_request.password:
                    user_data["password"] = user_request.password
                if user_request.roleName:
                    user_data["roleName"] = user_request.roleName
                
                # 调用新的API接口
                response = client.session.post(
                    f"{client.base_url}/api/public/addUser",
                    json={"list": [user_data]},
                    headers={"Authorization": config.MOEMAIL_EMAIL_LIST_TOKEN}  # 使用 emailList 的 token
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("code") == 200:
                    created_users.append({
                        "email": user_request.email,
                        "status": "created",
                        "message": "创建成功"
                    })
                else:
                    failed_users.append({
                        "email": user_request.email,
                        "error": result.get("message", "未知错误")
                    })
                    
            except Exception as e:
                failed_users.append({
                    "email": user_request.email,
                    "error": str(e)
                })
        
        # 返回结果
        if failed_users:
            return CreateUsersResponse(
                code=207,  # 部分成功
                message=f"部分用户创建成功：{len(created_users)}个成功，{len(failed_users)}个失败",
                data={
                    "created": created_users,
                    "failed": failed_users
                }
            )
        else:
            return CreateUsersResponse(
                code=200,
                message="所有用户创建成功",
                data={
                    "created": created_users,
                    "failed": []
                }
            )
            
    except Exception as e:
        logger.error(f"创建用户失败: {e}")
        raise HTTPException(status_code=500, detail=f"创建用户失败: {str(e)}")

@app.post("/api/public/createUser", response_model=CreateUsersResponse)
async def create_single_user(user_request: CreateUserRequest):
    """创建单个邮箱用户接口（便捷版）"""
    # 转换为批量请求格式
    batch_request = CreateUsersRequest(list=[user_request])
    return await create_email_users(batch_request)

@app.post("/api/public/emailList", response_model=EmailListResponse)
async def get_email_list(request: EmailListRequest):
    """获取邮件列表接口（新的API接口）"""
    try:
        # 使用主配置中的MoeMail设置
        # 创建 moemail客户端
        client = MoeMailClient(
            base_url=config.MOEMAIL_URL,
            api_key=config.MOEMAIL_API_KEY
        )
        
        # 调用新的emailList接口
        messages = client.get_messages(
            email_id=request.toEmail,  # 使用toEmail作为email_id
            limit=request.size,
            to_email=request.toEmail,
            send_email=request.sendEmail,
            send_name=request.sendName
        )
        
        # 转换为响应格式
        message_list = []
        for msg in messages:
            message_list.append({
                "uuid": msg.id,
                "sendEmail": msg.from_address,
                "sendName": "noreply",  # 默认值
                "subject": msg.subject,
                "timeStamp": msg.received_at,
                "content": msg.content,
                "type": "email",  # 默认类型
                "uuid": msg.id,
                "num": request.num
            })
        
        return EmailListResponse(
            code=200,
            message="success",
            data=message_list
        )
        
    except Exception as e:
        logger.error(f"获取邮件列表失败: {e}")
        return EmailListResponse(
            code=500,
            message=f"获取邮件列表失败: {str(e)}",
            data=None
        )

@app.get("/api/accounts/{email}")
async def get_account_info(email: str):
    """获取指定账号信息"""
    if not pool_manager:
        raise HTTPException(status_code=503, detail="服务不可用")
    
    try:
        account = pool_manager.db.get_account_by_email(email)
        
        if not account:
            raise HTTPException(status_code=404, detail=f"账号 {email} 不存在")
        
        return AccountInfo(
            email=account.email,
            local_id=account.local_id,
            id_token=account.id_token,
            refresh_token=account.refresh_token,
            status=account.status,
            created_at=account.created_at.isoformat() if account.created_at else None,
            last_used=account.last_used.isoformat() if account.last_used else None,
            last_refresh_time=account.last_refresh_time.isoformat() if account.last_refresh_time else None,
            use_count=account.use_count,
            session_id=account.session_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取账号信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取账号信息失败: {str(e)}")

# 错误处理
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": datetime.now().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理"""
    logger.error(f"未处理的异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "内部服务器错误",
            "detail": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

def main():
    """主函数"""
    logger.info(f"账号池服务启动配置:")
    logger.info(f"  主机: {config.POOL_SERVICE_HOST}")
    logger.info(f"  端口: {config.POOL_SERVICE_PORT}")
    logger.info(f"  最小池大小: {config.MIN_POOL_SIZE}")
    logger.info(f"  最大池大小: {config.MAX_POOL_SIZE}")
    logger.info(f"  每请求账号数: {config.ACCOUNTS_PER_REQUEST}")
    
    uvicorn.run(
        "main:app",
        host=config.POOL_SERVICE_HOST,
        port=config.POOL_SERVICE_PORT,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main()