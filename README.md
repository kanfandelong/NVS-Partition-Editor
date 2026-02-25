# NVS Partition Editor (nvs_edit)

ESP-IDF NVS分区图形化编辑工具

---

## 简介

NVS Partition Editor 是一个基于 Tkinter 的 GUI 工具，支持 ESP-IDF NVS 分区的解析、编辑、导入导出 CSV、分区生成等功能。适用于 Windows 平台，方便开发者管理 ESP32 NVS 分区数据。

## 功能特性
- 打开并解析 ESP-IDF NVS 分区 Bin 文件
- 查看、添加、编辑、删除 NVS 条目
- 命名空间分组、排序、实时搜索过滤
- CSV 导入导出，遵循官方命名空间分组规则
- 基于 CSV 重新生成 NVS 分区 Bin 文件
- 支持单文件打包（PyInstaller）

## 目录结构示例
- nvs_edit.py  主程序入口（GUI）
- nvs_parser.py   NVS 分区解析模块
- nvs_logger.py   日志/JSON 打印模块
- nvs_partition_gen.py  分区生成模块
- nvs_tool.py     相关工具
- requirements.txt 依赖清单
- build/  构建输出

## 安装与运行

### 环境准备
- Windows 操作系统
- Python 3.x（建议使用虚拟环境）

### 安装依赖
```shell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 运行
```shell
python nvs_edit.py
```

### 打包为单文件可执行
```shell
pyinstaller --onefile nvs_edit.py
```
生成的可执行文件在 dist/ 目录。

## 使用说明

- 打开分区：菜单“文件 -> 打开NVS分区”选择 .bin 文件
- 导入/导出 CSV：
  - 导入 CSV：自动识别命名空间，添加数据
  - 导出 CSV：按命名空间分组导出
- 编辑数据：
  - 工具栏“添加条目”“编辑条目”“删除条目”操作
  - 支持多种类型，blob/string 有 ASCII 预览
- 生成分区：
  - 指定分区大小，点击“生成NVS分区”
- 排序与搜索：
  - 工具栏排序字段、顺序按钮，搜索框实时过滤

## CSV 规范
- 列名：key, type, encoding, value
- 命名空间定义：命名空间名, namespace, ,
- 数据行：key, data, encoding, value
- encoding 支持：u8, i8, u16, i16, u32, i32, u64, i64, string, blob_data, hex2bin, binary, base64 等

## 数据处理流程
- 解析：读取分区 Bin，nvs_parser 转换为数据结构，nvs_logger 输出 JSON，提取命名空间
- 显示：条目映射到树状视图，支持排序和过滤
- 保存：数据转为 CSV，调用 nvs_partition_gen 生成分区 Bin

## 兼容性与注意事项
- 基于 Python 3.x 和 Tkinter，适用于 Windows
- CSV 格式需与程序导入导出逻辑一致
- 分区大小需合理

## 贡献
- 欢迎提问、提交 Issues/PR
- 改进建议请在 PR 中说明

## 许可证

本项目采用 GPL-v3 许可证。详情见 LICENSE 文件。

## 常见问题
- GUI 无法启动：请确认 Python 环境和 Tkinter 可用，依赖已安装
- 导出 CSV：加载分区后点击“导出CSV”
- 生成分区：导入/导出 CSV 后点击“生成NVS分区”

---

作者：看番の龙
联系我: 2037443617@qq.com

