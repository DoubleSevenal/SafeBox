# SafeBox

SafeBox 是一个本地优先的个人账号密码和小纸条管理软件，界面风格按 Windows 11 Fluent 方向设计。

中文名：私人保险箱。

## 当前功能

- 使用保险箱ID区分不同数据空间
- 使用保险箱密码打开对应保险箱
- 管理账号密码和分类
- 管理小纸条，支持新建、编辑、导入 `.txt` / `.md` / `.markdown`
- 回收站恢复和彻底删除
- 修改保险箱密码
- 设置备份位置、手动同步、关闭或锁定时自动同步

## 开发运行

```powershell
python -m pip install -e ".[dev]"
python -m pytest -p no:cacheprovider -v
$env:PYTHONPATH='src'; python -m safebox
```

如果国内网络安装依赖较慢，可以使用清华源：

```powershell
python -m pip install --user -i https://pypi.tuna.tsinghua.edu.cn/simple pytest cryptography ruff PySide6
```

## 数据位置

默认数据位于：

`%USERPROFILE%\AppData\Local\SafeBox\vaults\<保险箱ID>\vault.db`

每个保险箱ID对应一个本地数据库。设置备份位置后，会生成一个固定备份文件，例如：

`SafeBox-school.pmbackup`
