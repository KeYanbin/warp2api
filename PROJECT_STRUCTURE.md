# Warp2API 项目架构说明

## 项目结构

```
warp2api/
├── account-pool-service/          # 独立的账号池服务
│   ├── main.py                   # 服务主入口，FastAPI应用
│   ├── config.py                 # 配置管理
│   ├── requirements.txt          # Python依赖
│   ├── README.md                 # 服务文档
│   ├── account_pool/             # 账号池核心模块
│   │   ├── pool_manager.py       # 号池管理器（会话管理、自动补充）
│   │   ├── database.py           # 数据库操作（SQLite）
│   │   ├── batch_register.py     # 批量注册器（Firebase认证）
│   │   └── token_refresh_service.py # Token刷新服务
│   └── utils/                    # 工具模块
│       ├── logger.py            # 日志工具
│       └── helpers.py           # 辅助函数
│
├── z-warp2api/                   # Warp2API主服务
│   ├── main.py                  # 主入口
│   ├── server.py                # 服务器实现
│   ├── config.py                # 配置管理
│   ├── requirements.txt         # Python依赖
│   ├── account_pool_client.py   # 账号池服务客户端
│   ├── warp_api/                # Warp API相关
│   │   ├── client.py           # Warp客户端基类
│   │   ├── pool_client.py      # 基于账号池的客户端
│   │   └── server.py           # API服务器
│   └── protobuf2openai/         # OpenAI兼容层
│       └── app.py              # OpenAI接口实现
│
├── start_services.sh            # 启动脚本
├── stop_services.sh            # 停止脚本
├── test_pool_service.py        # 测试脚本
└── logs/                       # 日志目录（运行时创建）
    ├── pool-service.log       # 账号池服务日志
    └── warp2api.log          # 主服务日志
```

## 架构设计

### 1. 账号池服务 (Account Pool Service)
独立的微服务，负责管理Warp账号的全生命周期：

- **端口**: 8019
- **功能**:
  - 账号自动注册和激活
  - 账号池维护（自动补充、清理过期）
  - Token刷新（遵守1小时限制）
  - 会话管理（分配/释放账号）
  - RESTful API接口

### 2. Warp2API服务
主服务，提供OpenAI兼容的API接口：

- **端口**: 8018
- **功能**:
  - 从账号池服务获取账号
  - 转换Warp API为OpenAI格式
  - 处理聊天请求（流式/非流式）
  - 管理客户端会话

## 核心组件说明

### 账号池管理器 (PoolManager)
- 维护最小账号数量（默认5个）
- 自动补充不足的账号
- 清理过期会话（30分钟超时）
- 线程安全的并发控制

### 批量注册器 (BatchRegister)
- 使用MoeMail临时邮箱服务
- Firebase邮箱登录认证
- Warp用户激活（GraphQL API）
- 支持并发注册（默认3线程）

### Token刷新服务 (TokenRefreshService)
- 检查JWT token过期时间
- 严格遵守1小时刷新限制
- 自动刷新即将过期的token
- 记录刷新时间防止频繁刷新

### 账号池客户端 (AccountPoolClient)
- 异步和同步API支持
- 自动管理会话映射
- 连接池优化
- 错误重试机制

## API接口

### 账号池服务API

#### 健康检查
```http
GET http://localhost:8019/health
```

#### 分配账号
```http
POST http://localhost:8019/api/accounts/allocate
Content-Type: application/json

{
    "session_id": "optional_session_id",
    "count": 1
}
```

#### 释放账号
```http
POST http://localhost:8019/api/accounts/release
Content-Type: application/json

{
    "session_id": "session_id_to_release"
}
```

#### 获取状态
```http
GET http://localhost:8019/api/accounts/status
```

### Warp2API服务（OpenAI兼容）

#### 聊天完成
```http
POST http://localhost:8018/v1/chat/completions
Content-Type: application/json

{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
        {"role": "user", "content": "Hello!"}
    ],
    "stream": false
}
```

## 使用流程

### 1. 启动服务
```bash
./start_services.sh
```

### 2. 检查状态
```bash
# 账号池状态
curl http://localhost:8019/api/accounts/status | python3 -m json.tool

# 服务健康检查
curl http://localhost:8019/health
curl http://localhost:8018/health
```

### 3. 使用示例

#### Python示例
```python
import requests

# 使用OpenAI兼容接口
response = requests.post(
    "http://localhost:8018/v1/chat/completions",
    json={
        "model": "claude-3-5-sonnet-20241022",
        "messages": [
            {"role": "user", "content": "What is the weather today?"}
        ]
    }
)
print(response.json())
```

#### 直接使用账号池
```python
from account_pool_client import AccountPoolClient

client = AccountPoolClient("http://localhost:8019")

# 分配账号
success, session_id, accounts = client.allocate_accounts_sync()
if success:
    # 使用账号
    for account in accounts:
        print(f"Using account: {account.email}")
    
    # 释放账号
    client.release_accounts_sync(session_id)
```

### 4. 停止服务
```bash
./stop_services.sh
```

## 配置说明

### 环境变量
```bash
# 账号池服务
POOL_SERVICE_HOST=0.0.0.0
POOL_SERVICE_PORT=8019
MIN_POOL_SIZE=5
MAX_POOL_SIZE=50

# 主服务
HOST=0.0.0.0
PORT=8018
POOL_SERVICE_URL=http://localhost:8019
USE_POOL_SERVICE=true

# 日志级别
LOG_LEVEL=INFO
```

### 数据库
- 使用SQLite存储账号信息
- 文件路径: `accounts.db`
- 自动创建表结构和索引

## 监控和维护

### 日志查看
```bash
# 实时查看所有日志
tail -f logs/*.log

# 查看账号池服务日志
tail -f logs/pool-service.log

# 查看主服务日志
tail -f logs/warp2api.log
```

### 手动管理
```bash
# 手动补充账号
curl -X POST http://localhost:8019/api/accounts/replenish \
  -H "Content-Type: application/json" \
  -d '{"count": 10}'

# 刷新Token
curl -X POST http://localhost:8019/api/accounts/refresh-tokens \
  -H "Content-Type: application/json" \
  -d '{"force": false}'
```

## 注意事项

1. **Token刷新限制**: 严格遵守1小时刷新一次的限制，防止账号被封
2. **并发安全**: 使用线程锁和数据库事务确保并发安全
3. **自动维护**: 服务会自动维护账号池，无需人工干预
4. **错误处理**: 完善的错误处理和重试机制
5. **资源清理**: 会话超时自动清理，防止资源泄露

## 故障排查

### 服务无法启动
- 检查端口是否被占用: `lsof -i:8019` 和 `lsof -i:8018`
- 查看日志文件获取错误信息
- 确保Python依赖已安装

### 账号池不足
- 检查MoeMail服务是否可用
- 检查Firebase API密钥是否有效
- 手动补充账号: 使用 `/api/accounts/replenish` 接口

### Token过期
- 检查Token刷新服务是否正常
- 查看 `last_refresh_time` 确认刷新时间
- 必要时使用 `force` 参数强制刷新（谨慎使用）

## 开发说明

### 添加新功能
1. 账号池服务的修改在 `account-pool-service/` 目录
2. 主服务的修改在 `z-warp2api/` 目录
3. 确保更新相应的配置和文档

### 测试
```bash
# 运行测试脚本
python3 test_pool_service.py

# 单元测试（如果有）
python3 -m pytest tests/
```

## License

MIT