# 项目文档
## 概述
这是基于D:\study\Projects\Agent\Practice02的Agent开发实践，主要包含代码架构图和功能说明。

## 代码结构
以下是项目的代码结构图：
![](code_architecture.mmd)

## 主要功能
- `getDate`: 获取当前电脑的日期和时间
- `getCwd`: 获取当前工作目录
- `listDir`: 列出指定目录下所有文件和子目录
- `getFileType`: 获取指定文件的类型
- `readFile`: 读取指定文件的内容，仅支持纯文本格式文件
- `createFile`: 根据指定的目录和文件名创建新文件
- `editFile`: 编辑指定文件的内容，仅支持纯文本格式文件
- `createDir`: 创建新目录
- `removeDir`: 删除目录，包括非空目录
- `removeFile`: 删除文件
- `rename`: 重命名文件和目录