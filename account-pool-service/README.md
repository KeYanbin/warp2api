# 账号池服务 (Account Pool Service)

独立的Warp账号池管理服务，提供RESTful API接口供其他服务调用。

## 功能特性

- ✅ **账号自动管理**：自动注册、维护和刷新账号
- ✅ **多进程支持**：线程安全，支持多进程并发调用
- ✅ **RESTful API**：标准的HTTP接口，易于集成
- ✅ **自动补充**：账号不足时自动补充到配置的最小值
- ✅ **Token刷新**：自动刷新即将过期的Token（遵守1小时限制）
- ✅ **会话管理**：支持会话级别的账号分配和释放

## 安装

```bash
# 安装依赖
pip install -r requirements.txt
```

## 配置

通过环境变量或修改 `config.py` 文件进行配置：

```python
# 服务配置
POOL_SERVICE_HOST = "0.0.0.0"  # 监听地址
POOL_SERVICE_PORT = 8019       # 监听端口

# 号池配置
MIN_POOL_SIZE = 5      # 最少维持账号数
MAX_POOL_SIZE = 50     # 最大储备账号数
ACCOUNTS_PER_REQUEST = 1  # 每个请求分配账号数
```

## 启动服务

```bash
python main.py
```

服务将在 `http://localhost:8019` 启动。

## API 接口

### 1. 健康检查
```http
GET /health
```

### 2. 分配账号
```http
POST /api/accounts/allocate
Content-Type: application/json

{
    "session_id": "optional_session_id",  // 可选，不提供会自动生成
    "count": 1  // 需要的账号数量
}
```

响应示例：
```json
{
    "success": true,
    "session_id": "session_abc123",
    "accounts": [
        {
            "email": "user@example.com",
            "local_id": "firebase_uid",
            "id_token": "jwt_token",
            "refresh_token": "refresh_token",
            "status": "in_use",
            "use_count": 1
        }
    ],
    "message": "成功分配 1 个账号"
}
```

### 3. 释放账号
```http
POST /api/accounts/release
Content-Type: application/json

{
    "session_id": "session_abc123"
}
```

### 4. 获取账号池状态
```http
GET /api/accounts/status
```

响应示例：
```json
{
    "pool_stats": {
        "available": 10,
        "in_use": 2,
        "total": 12
    },
    "active_sessions": 2,
    "running": true,
    "health": "healthy",
    "timestamp": "2024-01-01T12:00:00"
}
```

### 5. 刷新Token
```http
POST /api/accounts/refresh-tokens
Content-Type: application/json

{
    "email": "specific@email.com",  // 可选，不指定则刷新所有
    "force": false  // 是否强制刷新（忽略时间限制）
}
```

### 6. 手动补充账号
```http
POST /api/accounts/replenish
Content-Type: application/json

{
    "count": 10  // 补充数量，可选
}
```

### 7. 获取指定账号信息
```http
GET /api/accounts/{email}
```

## 客户端调用示例

### Python
```python
import requests

# 分配账号
response = requests.post("http://localhost:8019/api/accounts/allocate", 
    json={"session_id": "my_session"})
data = response.json()

if data["success"]:
    accounts = data["accounts"]
    session_id = data["session_id"]
    
    # 使用账号...
    for account in accounts:
        print(f"使用账号: {account['email']}")
        # 你的业务逻辑
    
    # 使用完毕后释放
    requests.post("http://localhost:8019/api/accounts/release",
        json={"session_id": session_id})
```

### JavaScript/Node.js
```javascript
// 分配账号
const allocateResponse = await fetch('http://localhost:8019/api/accounts/allocate', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({session_id: 'my_session'})
});

const data = await allocateResponse.json();

if (data.success) {
    const {accounts, session_id} = data;
    
    // 使用账号
    for (const account of accounts) {
        console.log(`使用账号: ${account.email}`);
        // 你的业务逻辑
    }
    
    // 释放账号
    await fetch('http://localhost:8019/api/accounts/release', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id})
    });
}
```

## 架构说明

```
account-pool-service/
├── main.py                 # 主入口，FastAPI应用
├── config.py              # 配置文件
├── requirements.txt       # 依赖列表
├── account_pool/         # 账号池核心逻辑
│   ├── pool_manager.py   # 号池管理器
│   ├── database.py       # 数据库操作
│   ├── batch_register.py # 批量注册器
│   └── token_refresh_service.py # Token刷新服务
└── utils/                # 工具模块
    ├── logger.py        # 日志工具
    └── helpers.py       # 辅助函数
```

## 注意事项

1. **Token刷新限制**：严格遵守1小时刷新一次的限制，防止账号被封
2. **并发安全**：服务使用线程锁确保并发安全，可以多进程调用
3. **自动维护**：服务会自动维护账号池，清理过期会话和账号
4. **数据库**：使用SQLite存储账号信息，文件名为 `accounts.db`

## 监控和维护

- 定期检查 `/api/accounts/status` 接口，监控账号池健康状态
- 当 `health` 状态为 `low` 或 `critical` 时，考虑手动补充账号
- 查看日志文件 `account-pool-service.log` 了解详细运行状态

## License

MIT