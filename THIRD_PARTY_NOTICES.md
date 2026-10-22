# 第三方依赖与分发边界

| 项目 | 用途 | 许可/取得方式 |
| --- | --- | --- |
| Python | 运行时与标准库 | PSF 许可；用户独立安装 |
| Shapely | 几何检查与处理 | BSD-3-Clause；通过 requirements 安装 |
| GEOS | Shapely 底层几何库 | LGPL-2.1；由相应 Shapely 分发包提供，遵守其通知 |
| Matplotlib | 预览绘图 | Matplotlib 许可，基于 PSF；用户独立安装 |
| NumPy、Pillow、ContourPy 等 | 上述库的传递依赖 | 以安装发行包的许可证为准；本包不捆绑 |
| PLAXIS / plxscripting | 原生建模与官方 SDK | 厂商许可；本包不附带、不重新授权 |
| @oai/artifact-tool | 模板作者脚本 | 单独取得的作者工具；本包不附带，不作为最终用户运行依赖 |

源码中的依赖调用不表示第三方代码按 MIT 重新授权。本包不含第三方二进制及其源代码；若以后捆绑 Python 或 wheel，必须重新核对并保留各发行包及所含原生库的许可通知。

官方许可信息：
- https://docs.python.org/3/license.html
- https://github.com/shapely/shapely/blob/main/LICENSE.txt
- https://libgeos.org/project/license/
- https://matplotlib.org/stable/project/license.html
- https://opensource.org/license/mit

本包没有包含 PLAXIS 程序、SDK、厂商手册、破解文件、逆向输出、第三方本构 DLL、真实工程或原始钻孔数据。PLAXIS 是其权利人的产品名称。
