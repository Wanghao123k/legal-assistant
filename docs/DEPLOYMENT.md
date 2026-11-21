# 阿里云 ECS 自动部署

将代码推送到 GitHub 的 `master` 分支后，GitHub Actions 构建现有 `Dockerfile`，检查网页能否打开，通过 SSH 上传镜像，在 ECS 上替换聊天容器。前后端仍然共用一个镜像和一个容器。

业务环境变量只在服务器 `/opt/legal-assistant/.env` 手动配置。工作流不上传、不覆盖这个文件，也不需要将模型密钥放到 GitHub。

## 1. 准备服务器

本方案适用于 **Linux x86_64 / amd64 ECS**，与 GitHub 的 Ubuntu 构建机架构一致。如果服务器是 ARM，需要先调整镜像构建架构。

安装并启动 Docker Engine，在服务器执行 `docker version` 确认客户端和服务端均正常。根据操作系统参考 [Docker 官方安装说明](https://docs.docker.com/engine/install/)，选择对应发行版；本方案无需安装 Compose，也无需在 ECS 上安装 Git 或 Python。

以下示例使用 `deploy` 用户。已有合适的 SSH 用户也可以直接使用，并相应替换用户名。先以 root 执行：

```bash
useradd -m -s /bin/bash deploy
usermod -aG docker deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
install -d -m 700 -o deploy -g deploy /opt/legal-assistant
```

如果 `deploy` 已存在，跳过 `useradd`。加入 docker 组后需重新登录。docker 组可控制整台主机，仅授予用于部署的可信账号。

在阿里云安全组和服务器防火墙允许：

- SSH 端口（默认 TCP 22）：GitHub 托管运行器必须能连接该端口。其出口地址会变动，只允许你自己电脑的 IP 无法完成自动部署；若要求固定来源 IP，可改用固定出口的运行器。
- TCP 8000：用于访问当前聊天页面，可以限制为自己的公网 IP。

本方案只操作 `legal-assistant` 及其临时备份容器。仓库原有的 `docker-compose.yml` 属于 Milvus，不参与本次应用部署。

## 2. 手动配置业务环境变量

以 `deploy` 用户登录服务器：

```bash
umask 077
touch /opt/legal-assistant/.env
chmod 600 /opt/legal-assistant/.env
vi /opt/legal-assistant/.env
```

填写你实际使用的配置：

```dotenv
LLM_API_KEY=替换为你的真实模型密钥
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=替换为你的账号可用的模型名称
```

使用 `KEY=value` 格式，不加 `export`、引号或行尾注释。Docker 的 `--env-file` 与 shell 配置文件解析规则不同。数据库等其他配置，等应用代码开始读取后也可以放在这里。

文件会在每次创建容器时通过 `--env-file` 注入；镜像中不包含它。脚本固定容器内部 `HOST=0.0.0.0`、`PORT=8000`，无需在 `.env` 设置这两个值。

当前应用仅实现聊天，尚未加入登录鉴权；公网开放聊天接口后，访问者可以消耗你的模型额度。首次部署可以把 8000 的访问来源限制为自己的 IP。

## 3. 配置 SSH 部署密钥

在自己的电脑上生成一对专用于这个项目的密钥：

```bash
ssh-keygen -t ed25519 -C "legal-assistant-actions" -f legal-assistant-actions
```

提示输入口令时直接回车，生成供自动部署使用的无口令密钥。公钥文件为 `legal-assistant-actions.pub`，私钥为 `legal-assistant-actions`。在项目目录之外生成，勿提交私钥。

把公钥文件中的**一整行**追加到服务器 `/home/deploy/.ssh/authorized_keys`，然后以 root 执行：

```bash
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
```

验证该密钥能登录，且部署用户拥有 Docker 权限：

```bash
ssh -i legal-assistant-actions -p 22 deploy@你的服务器公网IP "docker info >/dev/null && test -r /opt/legal-assistant/.env"
```

### 获取服务器主机公钥

服务器的主机公钥用于确认连接的是你的 ECS，与上面的用户部署密钥不同。

在可信的 ECS 控制台终端执行：

```bash
cat /etc/ssh/ssh_host_ed25519_key.pub
```

将返回的 `ssh-ed25519 AAAA...` 拼成一行，准备填入 `SSH_KNOWN_HOSTS`：

```text
你的服务器公网IP ssh-ed25519 AAAA...实际主机公钥...
```

如果 SSH 使用非 22 端口，例如 2222，格式为：

```text
[你的服务器公网IP]:2222 ssh-ed25519 AAAA...实际主机公钥...
```

IP 或域名必须与 `SSH_HOST` 完全一致。工作流启用严格主机校验，主机重装或更换主机密钥后，需要重新核对并更新该值。

## 4. 配置 GitHub Secrets

打开 [仓库 Actions Secrets 设置](https://github.com/Wanghao123k/legal-assistant/settings/secrets/actions)，即 `Settings → Secrets and variables → Actions → New repository secret`，添加：

| Secret 名称 | 内容 |
|---|---|
| `SSH_HOST` | ECS 公网 IPv4 地址或域名，不带 `http://` |
| `SSH_PORT` | SSH 端口，通常为 `22`，不填时默认 22 |
| `SSH_USER` | 部署用户名，如 `deploy` |
| `SSH_PRIVATE_KEY` | `legal-assistant-actions` 私钥的完整内容，包括 BEGIN/END 两行 |
| `SSH_KNOWN_HOSTS` | 上一步准备的主机公钥记录 |

这里配置的是连接服务器所需的信息。`LLM_API_KEY` 等业务环境变量继续由你在服务器手动维护。

## 5. 首次发布

把新增的工作流、脚本和文档提交到 `master` 并推送：

```bash
git add .github/workflows/deploy.yml scripts/deploy.sh .gitattributes docs/DEPLOYMENT.md
git commit -m "Add automatic deployment to Aliyun"
git push origin master
```

打开仓库 [Actions 页面](https://github.com/Wanghao123k/legal-assistant/actions) 查看 `Deploy to Aliyun`。

首次运行会上传镜像并创建 `legal-assistant`；之后每次推送到 `master`（包括合并 PR）都会重新构建和发布。只在电脑上 `git commit` 不会触发，需要推送到 GitHub。也可在工作流页面使用 `Run workflow`，选择 `master` 手动重试。

服务器不需要从 GitHub 拉代码，也不需要从镜像仓库拉镜像。镜像通过 SSH 传输，传输耗时取决于镜像大小和服务器带宽。构建机需要能访问 Docker Hub 和 Python 包源。

成功后访问 `http://你的服务器公网IP:8000`。确认网页打开后，再发送一条消息检查模型配置。

```bash
docker ps --filter name=legal-assistant
docker logs --tail 100 legal-assistant
docker inspect --format '{{.State.Health.Status}}' legal-assistant
```

健康检查只验证网页服务能够响应，不会调用付费模型，不能验证密钥、余额、模型权限或外网到服务器的连通性。

## 6. 以后修改环境变量

编辑 `/opt/legal-assistant/.env` 后，使用当前已发布镜像重新创建容器即可，无需修改代码或提交 `.env`：

```bash
image=$(cat /opt/legal-assistant/.deployed-image)
bash /opt/legal-assistant/deploy.sh "${image#legal-assistant:}"
```

也可以在 GitHub Actions 手动运行工作流。单独 `docker restart` 不会重新读取 `--env-file`。勿在自动部署运行时同时修改 `.env`。

## 7. 失败与回退

构建、上传、配置预检查失败时，旧容器继续运行。替换容器时有短暂中断；新容器未通过启动检查时，脚本会删除新容器并尝试恢复旧容器。第一次部署没有旧容器可恢复。应用数据迁移及零停机发布不在当前聊天服务方案内。

若需要在成功发布后回退到上一个镜像，在服务器执行：

```bash
image=$(cat /opt/legal-assistant/.previous-image)
bash /opt/legal-assistant/deploy.sh "${image#legal-assistant:}"
```

旧镜像会保留在服务器，回退仍读取当前 `.env`；需要回退配置时由你手动恢复该文件。随发布次数增加，定期使用 `docker system df` 查看空间，确认无需回退后再按具体标签删除不用的应用镜像。

如果主机掉电或部署进程被强制结束，可能留下 `legal-assistant-previous`。脚本会停止后续部署，防止覆盖备份。在确认没有部署正在运行后，检查两个容器，再决定保留哪个：

```bash
docker ps -a --filter name=legal-assistant
docker logs --tail 100 legal-assistant
```

恢复备份的示例（会删除当前同名应用容器）：

```bash
docker rm -f legal-assistant
docker rename legal-assistant-previous legal-assistant
docker start legal-assistant
```

若当前容器已验证正常，则只删除已停止的 `legal-assistant-previous`。失败或中断的上传包可能留在 `/opt/legal-assistant/incoming/`，确认任务结束后可删除对应目录里的 `image.tar.gz` 和 `deploy.sh`，成功发布的上传包会自动清理。

参考：[GitHub Actions 触发条件](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)、[GitHub Secrets](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)、[Docker run](https://docs.docker.com/reference/cli/docker/container/run/)。
