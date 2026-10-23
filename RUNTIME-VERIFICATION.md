# B04已有候选镜像：隔离运行验证方案

R01（run39899566373）已结束，整体failure；本修正版仅离线准备，尚未上传或启动第二次验证。

手动流程`runtime-smoke.yml`只拉取既有B04固定镜像，不构建、不推送镜像：

`ghcr.io/sansyuan97-code/dify-finish-reason-candidate@sha256:3ebe4e18ef2894409ecb1b3b82523c463dc7a47afa2aba50e7d22b489eb483f7`

预期image/config ID：`sha256:7ef22d325bc9a03ba48a9a58603be3ffb75e5db13eb42bf6f5d8d519e55afd87`。

一次手动授权后，在公开仓库的标准`ubuntu-24.04`运行环境输入`VERIFY-B04-ONCE`执行。任务最长20分钟，只接受attempt 1。没有自动重试、push触发、付费运行环境、缓存上传或Actions附件。

拉取前拟要求当前可用内存至少3GiB、磁盘至少10GiB。这是方案起步门槛，不是已测最低需求。Next和实验性Vinext顺序测试，同时最多一个应用容器；各容器限制2GiB内存、无额外swap、2核、256进程。目标失败不重启；同一次任务仍可独立检查另一个目标。启动等待仅针对连接拒绝/重置，最长120秒；HTTP或内容检查失败不重试。

读取私有镜像使用仓库临时`GITHUB_TOKEN`和`packages: read`权限，不使用个人令牌。镜像需事先允许该仓库的Actions读取；权限失败就停止，不自动将镜像公开或扩大授权。应用启动前退出镜像仓库登录，清理阶段删除专用临时凭据目录。令牌和Docker接口不会挂载进应用容器。

两个容器均以非root的`dify`用户运行官方入口，不提供主机挂载、开放端口、后端、模型凭据、个人资料或工作流记录。`--network none`仅保留容器自身回环网络；API与市场地址指向容器内部未使用的回环端口。HTTP检查在各容器内执行，仅访问自身服务。

核对内容包括：固定镜像/config身份、官方入口文件摘要、所选服务器进程、用户、网络/资源设置；`/signin`返回200 HTML，其引用的一份本地JavaScript脚本返回200。没有测试浏览器渲染和交互。缺少后端时HTML可能只有应用加载外壳，不能证明登录可用。分别记录两个目标；总体通过还要求两者及容器/凭据清理均已核实。清理由脚本finally和工作流always步骤执行；若运行环境中断导致证据未捕获，清理与运行仍标未核实。

本项不等于部署、生产服务回退演练、编辑器变量菜单检查、项目类型检查、真实14节点业务运行或服务商账单核验。此流程不会将私有镜像下载到用户电脑。原构建流程、固定源码包、4行补丁、官方Dockerfile和依赖锁保持原样。

修正版离线准备通过8组执行门槛/防误判测试，以及Python和Node探针语法检查。这些结果不能证明云端流程或镜像实际运行成功。

依据：[Docker无网络模式](https://docs.docker.com/engine/network/drivers/none/)、[GitHub私有包授权](https://docs.github.com/en/packages/learn-github-packages/introduction-to-github-packages)、[公开仓库标准运行环境](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)。


## R01结果与检查修正

R01私有镜像拉取成功，固定digest/config匹配；Vinext的页面外壳与静态脚本检查通过。Next启动日志显示Ready，但检查器将正常的进程标题改写与错误身份混为一谈，最终报unexpected server/user。Next原探针结果没有在失败前写入报告，无法补回PID/UID等原始值；不能追认为Next已完整通过。

修正版按固定Next 16.3.4的官方行为识别next-server标题，并核对PID 1实际可执行文件与探针Node一致、UID1001及官方入口摘要。Vinext保留精确入口身份检查。所有探针先入报告再判断身份，失败也留原始值。两种目标、资源、网络、清理和总体通过标准保留。

另将测试用API/市场回环地址从端口9改为5001；前者触发Fetch的bad port日志。后端仍不存在，网络仍为none；不增加后端或模型调用。

依据：[固定Next 16.3.4官方入口](https://github.com/vercel/next.js/blob/v16.3.4/packages/next/src/server/lib/start-server.ts#L191)、[Node进程标题说明](https://nodejs.org/docs/latest-v24.x/api/process.html#processtitle)。原失败回执和输入保留；第二次运行需另获一次明确授权，不自动重跑，也不重新构建镜像。
