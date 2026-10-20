浙智研析 — Windows 64 位便携版

1. 将 ZIP 完整解压到本机文件夹，不要直接在压缩包里运行。
2. 双击 ZheZhiYanXi.exe，浏览器会自动打开应用。
3. 保持启动窗口开启；关闭该窗口即可停止应用。
4. 首次使用，在“模型与资料设置”填写自己的 API Key 并选择资料目录。

无需安装 Python、pip、Codex 或其他依赖；PDF、Excel 和 OCR 组件已包含。
必须保留 EXE 旁的 _internal 文件夹，不能只复制一个 EXE 给其他人。
本地文档解析和 OCR 可离线使用；模型分析和在线检索需要网络以及相应 API Key。

支持 Windows 10/11 x64。当前应用未进行商业代码签名。
设置、缓存与报告位于 %LOCALAPPDATA%\ZheZhiYanXi。
EXE 版默认资料目录位于 %LOCALAPPDATA%\ZheZhiYanXi\资料库。
已有源码版配置会继续使用，无需重复填写密钥。升级前先关闭旧应用。

诊断：在此文件夹打开终端，执行 ZheZhiYanXi.exe --self-test，
可离线检查 PDF、Excel、OCR 模型与界面资源。

源码与说明：https://github.com/qcyay/zhezhi-yanxi
