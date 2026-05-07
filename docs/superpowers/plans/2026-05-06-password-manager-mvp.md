# SafeBox MVP Implementation Plan

> 当前计划已按产品取舍更新：第一版不包含“标签”和“生成密码”功能。

**Goal:** 构建一个本地离线优先的个人账号密码和安全小纸条管理器。

**Tech Stack:** Python、PySide6、SQLite、cryptography、pytest、ruff。

## 第一版范围

- 打开软件时输入总密码
- 总密码错误时提示，不闪退
- 快速新增账号记录
- 新增安全小纸条
- 账号详情页支持编辑、复制账号、复制密码、删除
- 小纸条详情页支持随时编辑、保存、删除
- 使用分类整理记录
- 默认分类包含：学校、工作、游戏、生活、软件、其他
- 安全小纸条默认分类为：收件箱
- 搜索名称、账号、分类、备注、入口说明
- 复制账号和密码
- 本地加密保存
- 自动锁定
- 剪贴板自动清除
- Windows 11 浅色 Fluent 风格界面

## 当前交互结构

- 左侧是模块导航：账号密码、小纸条、设置、锁定
- 账号密码模块进入账号列表页，点记录后进入账号详情页
- 列表单击记录即可进入详情页
- 账号列表只突出显示名称，分类显示在记录右侧彩色框中
- 账号详情页直接显示密码，并用字段卡片展示账号、密码、分类、入口说明
- 账号详情页点击编辑后直接在字段卡片内编辑，不再弹出编辑窗口
- 分类颜色按分类名称稳定映射，同类同色，使用 Win11 风格浅色配色
- 总密码解锁和创建保险箱弹窗使用现代化信息头
- 小纸条模块进入小纸条列表页，点记录后进入可编辑小纸条页面
- 小纸条编辑页提供基础排版按钮：加粗、斜体、下划线、项目符号、标题、正文
- 不再使用三栏布局，不再有固定最右侧详情栏
- 小纸条页面不会出现复制账号、复制密码按钮

## 明确不做

- 不做标签功能
- 不做生成密码功能
- 不做云同步
- 不做手机 App
- 不做浏览器插件

## 当前模块

- `src/safebox/core/models.py`：账号记录和安全小纸条的数据结构
- `src/safebox/core/crypto.py`：总密码派生密钥、加密、解密、密码校验
- `src/safebox/core/store.py`：SQLite 加密存储
- `src/safebox/core/services.py`：创建、搜索、读取、删除、解锁等业务逻辑
- `src/safebox/core/settings.py`：默认数据路径和安全时间设置
- `src/safebox/ui/app.py`：PySide6 启动入口
- `src/safebox/ui/main_window.py`：主窗口
- `src/safebox/ui/dialogs.py`：总密码、账号、小纸条弹窗
- `src/safebox/ui/clipboard.py`：剪贴板自动清除
- `src/safebox/ui/theme.py`：Win11 浅色样式

## 验证命令

```powershell
$env:PYTHONPATH='E:\MyCode\Python\SafeBox\src'
& 'E:\ProfessionalSoft\environoment\python\python.exe' -m pytest -p no:cacheprovider -v
& 'E:\ProfessionalSoft\environoment\python\python.exe' -m ruff check .
```
