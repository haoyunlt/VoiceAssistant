# 安全与权限系统 🔐

> **JWT 认证 + RBAC 权限控制** - 完整的安全解决方案

---

## 📋 概述

本系统提供完整的安全与权限管理，包括：

- **JWT 认证**: 基于 Token 的身份验证
- **RBAC 权限控制**: 基于角色的访问控制
- **多语言支持**: Go 和 Python 实现
- **中间件集成**: 无缝集成到现有服务
- **灵活的权限模型**: 可扩展的角色和权限

---

## 🚀 快速开始

### 1. 配置环境变量

```bash
# .env 文件
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ACCESS_EXPIRY=3600        # 1 hour
JWT_REFRESH_EXPIRY=604800     # 7 days
```

### 2. Go 服务集成

```go
package main

import (
    "time"
    "voice-assistant/pkg/auth"
    "voice-assistant/pkg/middleware"
    "github.com/gin-gonic/gin"
)

func main() {
    // Initialize JWT manager
    jwtManager := auth.NewJWTManager(
        "your-secret-key",
        time.Hour,      // access token expiry
        time.Hour * 24 * 7, // refresh token expiry
    )

    // Initialize RBAC manager
    rbacManager := auth.NewRBACManager()

    // Create router
    r := gin.Default()

    // Protected routes
    protected := r.Group("/api/v1")
    protected.Use(middleware.AuthMiddleware(jwtManager))
    {
        // Require specific permission
        protected.POST("/admin/users",
            middleware.RequirePermission(rbacManager, auth.PermissionWriteUser),
            createUserHandler,
        )

        // Require role
        protected.GET("/admin/dashboard",
            middleware.RequireRole(auth.RoleAdmin),
            dashboardHandler,
        )
    }

    r.Run(":8080")
}
```

### 3. Python 服务集成

```python
from fastapi import FastAPI, Depends
from fastapi.security import HTTPBearer

from app.auth.jwt_manager import get_jwt_manager
from app.auth.rbac import Permission, get_rbac_manager
from app.middleware.auth import verify_token, require_permission

app = FastAPI()
security = HTTPBearer()

# Protected endpoint
@app.post("/api/v1/execute")
async def execute_task(
    request: dict,
    user: dict = Depends(verify_token),
    _ = Depends(require_permission(Permission.USE_AGENT))
):
    return {"message": "Task executed", "user": user}
```

---

## 👥 角色与权限

### 预定义角色

| 角色          | 说明     | 权限级别       |
| ------------- | -------- | -------------- |
| **admin**     | 管理员   | 完全访问权限   |
| **developer** | 开发者   | 开发和测试权限 |
| **user**      | 普通用户 | 标准功能权限   |
| **guest**     | 访客     | 只读权限       |

### 权限列表

#### 用户权限

- `user:read` - 读取用户信息
- `user:write` - 修改用户信息
- `user:delete` - 删除用户

#### 聊天权限

- `chat:use` - 使用聊天功能
- `chat:history` - 访问聊天历史

#### 知识图谱权限

- `kg:read` - 读取知识图谱
- `kg:write` - 修改知识图谱
- `kg:delete` - 删除知识图谱

#### RAG 权限

- `rag:use` - 使用 RAG 功能
- `rag:manage` - 管理 RAG 配置

#### Agent 权限

- `agent:use` - 使用 Agent 功能
- `agent:manage` - 管理 Agent 配置

#### 系统权限

- `system:metrics` - 查看系统指标
- `system:manage` - 管理系统设置

### 角色权限矩阵

| 权限           | admin | developer | user | guest |
| -------------- | ----- | --------- | ---- | ----- |
| user:read      | ✅    | ✅        | ✅   | ❌    |
| user:write     | ✅    | ❌        | ❌   | ❌    |
| user:delete    | ✅    | ❌        | ❌   | ❌    |
| chat:use       | ✅    | ✅        | ✅   | ✅    |
| chat:history   | ✅    | ✅        | ✅   | ❌    |
| kg:read        | ✅    | ✅        | ✅   | ✅    |
| kg:write       | ✅    | ✅        | ❌   | ❌    |
| kg:delete      | ✅    | ❌        | ❌   | ❌    |
| rag:use        | ✅    | ✅        | ✅   | ❌    |
| rag:manage     | ✅    | ✅        | ❌   | ❌    |
| agent:use      | ✅    | ✅        | ✅   | ❌    |
| agent:manage   | ✅    | ✅        | ❌   | ❌    |
| system:metrics | ✅    | ✅        | ❌   | ❌    |
| system:manage  | ✅    | ❌        | ❌   | ❌    |

---

## 🔑 JWT 认证

### Token 结构

```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "username": "john_doe",
  "email": "john@example.com",
  "roles": ["user", "developer"],
  "exp": 1698765432,
  "iat": 1698761832,
  "iss": "voice-assistant",
  "sub": "123e4567-e89b-12d3-a456-426614174000"
}
```

### 生成 Token

**Go**:

```go
token, err := jwtManager.GenerateAccessToken(
    "user-id",
    "username",
    "email@example.com",
    []string{"user"},
)
```

**Python**:

```python
jwt_manager = get_jwt_manager()
token = jwt_manager.generate_access_token(
    "user-id",
    "username",
    "email@example.com",
    ["user"]
)
```

### 验证 Token

**Go**:

```go
claims, err := jwtManager.ValidateToken(tokenString)
if err != nil {
    // Handle error
}
```

**Python**:

```python
try:
    claims = jwt_manager.validate_token(token)
except ValueError as e:
    # Handle error
```

### Refresh Token

**Go**:

```go
newToken, err := jwtManager.RefreshAccessToken(
    refreshToken,
    "username",
    "email",
    []string{"user"},
)
```

**Python**:

```python
new_token = jwt_manager.refresh_access_token(
    refresh_token,
    "username",
    "email",
    ["user"]
)
```

---

## 🛡️ API 使用

### 登录获取 Token

```bash
# Request
POST /auth/login
Content-Type: application/json

{
  "username": "john_doe",
  "password": "password123"
}

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### 使用 Token 访问 API

```bash
curl -X POST http://localhost:8003/api/v1/execute \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello"}'
```

### 刷新 Token

```bash
# Request
POST /auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

## 🔧 中间件使用

### Go 中间件

#### 1. 认证中间件

```go
// 要求用户已认证
router.Use(middleware.AuthMiddleware(jwtManager))
```

#### 2. 可选认证中间件

```go
// 认证可选，但如果提供则验证
router.Use(middleware.OptionalAuthMiddleware(jwtManager))
```

#### 3. 权限中间件

```go
// 要求特定权限
router.Use(middleware.RequirePermission(rbacManager, auth.PermissionChat))

// 要求任意权限
router.Use(middleware.RequireAnyPermission(
    rbacManager,
    auth.PermissionChat,
    auth.PermissionReadKG,
))

// 要求特定角色
router.Use(middleware.RequireRole(auth.RoleAdmin))
```

### Python 中间件

#### 1. FastAPI Depends

```python
from fastapi import Depends
from app.middleware.auth import verify_token, require_permission
from app.auth.rbac import Permission

@app.post("/api/execute")
async def execute(
    user: dict = Depends(verify_token),
    _ = Depends(require_permission(Permission.USE_AGENT))
):
    return {"user_id": user["user_id"]}
```

#### 2. 中间件

```python
from fastapi import FastAPI
from app.middleware.auth import AuthMiddleware

app = FastAPI()
app.add_middleware(AuthMiddleware)
```

---

## 📝 完整示例

### Go Service

```go
package main

import (
    "net/http"
    "time"

    "github.com/gin-gonic/gin"
    "voice-assistant/pkg/auth"
    "voice-assistant/pkg/middleware"
)

func main() {
    // Initialize
    jwtManager := auth.NewJWTManager(
        "secret-key",
        time.Hour,
        time.Hour*24*7,
    )
    rbacManager := auth.NewRBACManager()

    r := gin.Default()

    // Public routes
    r.POST("/auth/login", loginHandler(jwtManager))
    r.POST("/auth/refresh", refreshHandler(jwtManager))

    // Protected routes
    api := r.Group("/api/v1")
    api.Use(middleware.AuthMiddleware(jwtManager))
    {
        // User endpoints
        api.GET("/profile", getProfileHandler)
        api.PUT("/profile",
            middleware.RequirePermission(rbacManager, auth.PermissionWriteUser),
            updateProfileHandler,
        )

        // Admin endpoints
        admin := api.Group("/admin")
        admin.Use(middleware.RequireRole(auth.RoleAdmin))
        {
            admin.GET("/users", listUsersHandler)
            admin.DELETE("/users/:id", deleteUserHandler)
        }
    }

    r.Run(":8080")
}

func loginHandler(jwtManager *auth.JWTManager) gin.HandlerFunc {
    return func(c *gin.Context) {
        var req struct {
            Username string `json:"username"`
            Password string `json:"password"`
        }

        if err := c.ShouldBindJSON(&req); err != nil {
            c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
            return
        }

        // Validate credentials (implement your logic)
        userID := "user-123"
        roles := []string{"user"}

        // Generate tokens
        accessToken, _ := jwtManager.GenerateAccessToken(
            userID, req.Username, "user@example.com", roles,
        )
        refreshToken, _ := jwtManager.GenerateRefreshToken(userID)

        c.JSON(http.StatusOK, gin.H{
            "access_token":  accessToken,
            "refresh_token": refreshToken,
            "token_type":    "bearer",
            "expires_in":    3600,
        })
    }
}
```

### Python Service

```python
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.auth.jwt_manager import get_jwt_manager
from app.auth.rbac import Permission, get_rbac_manager
from app.middleware.auth import verify_token, require_permission

app = FastAPI()
security = HTTPBearer()

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/auth/login")
async def login(request: LoginRequest):
    # Validate credentials (implement your logic)
    user_id = "user-123"
    roles = ["user"]

    jwt_manager = get_jwt_manager()

    access_token = jwt_manager.generate_access_token(
        user_id, request.username, "user@example.com", roles
    )
    refresh_token = jwt_manager.generate_refresh_token(user_id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": 3600
    }

@app.get("/api/v1/profile")
async def get_profile(user: dict = Depends(verify_token)):
    return {"user_id": user["user_id"], "username": user["username"]}

@app.post("/api/v1/execute")
async def execute(
    request: dict,
    user: dict = Depends(verify_token),
    _ = Depends(require_permission(Permission.USE_AGENT))
):
    return {"message": "Executed", "user": user}
```

---

## 🧪 测试

### 测试脚本

```bash
#!/bin/bash

# 1. 登录获取 token
TOKEN=$(curl -s -X POST http://localhost:8003/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' \
  | jq -r '.access_token')

echo "Token: $TOKEN"

# 2. 使用 token 访问受保护的 API
curl -X POST http://localhost:8003/api/v1/execute \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello"}'

# 3. 访问需要特定权限的 API
curl -X POST http://localhost:8006/api/v1/kg/extract \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text": "John works at Google"}'
```

---

## 🔒 安全最佳实践

### 1. Secret Key 管理

```bash
# 生成强密钥
openssl rand -hex 32

# 使用环境变量
export JWT_SECRET_KEY=$(openssl rand -hex 32)
```

### 2. Token 过期时间

```go
// 推荐设置
accessExpiry := time.Hour            // 1 hour
refreshExpiry := time.Hour * 24 * 7  // 7 days
```

### 3. HTTPS Only

```go
// 生产环境强制 HTTPS
router.Use(func(c *gin.Context) {
    if c.Request.Header.Get("X-Forwarded-Proto") != "https" {
        c.Redirect(301, "https://"+c.Request.Host+c.Request.URL.Path)
        return
    }
    c.Next()
})
```

### 4. Rate Limiting

```go
// 限制登录尝试
store := ratelimit.NewMemoryStore()
limiter := ratelimit.New(store, 5, time.Minute) // 5 attempts per minute

router.POST("/auth/login", limiter.Middleware(), loginHandler)
```

### 5. Token 黑名单

```go
// 实现 token 撤销（使用 Redis）
func RevokeToken(token string) error {
    return redisClient.Set(ctx, "revoked:"+token, "1", time.Hour*24).Err()
}

func IsTokenRevoked(token string) bool {
    val, _ := redisClient.Get(ctx, "revoked:"+token).Result()
    return val != ""
}
```

---

## 🛠️ 自定义角色和权限

### 添加新角色

**Go**:

```go
rbacManager := auth.NewRBACManager()
rbacManager.AddPermissionToRole(auth.Role("custom_role"), auth.Permission("custom:permission"))
```

**Python**:

```python
rbac_manager = get_rbac_manager()
rbac_manager.add_permission_to_role(Role.CUSTOM, Permission.CUSTOM_ACTION)
```

### 动态权限检查

```go
func CheckDynamicPermission(c *gin.Context, resource, action string) bool {
    roles, _ := middleware.GetUserRoles(c)
    permission := auth.Permission(resource + ":" + action)

    return rbacManager.CheckUserPermission(roles, permission)
}
```

---

## 📚 参考资料

- **JWT**: https://jwt.io/
- **RBAC**: https://en.wikipedia.org/wiki/Role-based_access_control
- **OWASP**: https://owasp.org/www-project-top-ten/

---

## 📞 支持

**文档**: 本 README
**Go 实现**: `pkg/auth/`, `pkg/middleware/`
**Python 实现**: `algo/agent-engine/app/auth/`, `algo/agent-engine/app/middleware/`

---

**版本**: v1.0.0
**最后更新**: 2025-10-27
**状态**: ✅ 生产就绪
