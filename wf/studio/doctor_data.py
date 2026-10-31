"""Read-only configuration checks; no server requests or view construction."""
from pathlib import Path

from wf import paths


def checks(add, *, fast=False, source=None, server_dir=None):
    def directory(key, explicit=None):
        value = Path(explicit) if explicit is not None else paths.configured_path(key)
        ok = value is not None and value.is_dir()
        return ("ok" if ok else "fail", f"{key}: 目录存在" if ok else f"{key}: 未配置或目录不存在")

    def profile():
        data, _ = paths.profile_data()
        return ("ok", "路径配置已读取") if data else ("warn", "未找到路径配置，仍可通过环境变量配置")

    add("profile", profile, "复制 profiles/example.json 为 profiles/local.json，或设置 WF_PATHS_PROFILE")
    add("store131", lambda: directory("store131"), "配置 paths.store131 或 WF_STORE131 为基线 upload 目录")
    add("server", lambda: directory("server", server_dir), "配置 paths.server / WF_SERVER 或 --server-dir 为只读镜像")

    def named_views():
        from wf.view.config import view_options
        selected, options = view_options()
        data, _ = paths.profile_data()
        views = data.get("views", {})
        for name in views:
            view_options(name)
        return ("ok" if selected else "warn", f"命名视图 {len(views)} 个；选中 {selected or '未指定（使用默认视图）'}")

    add("views", named_views, "配置 views 与 default_view；也可用 --view 或 WF_STUDIO_VIEW")

    def client():
        from wf.caps.profiles import resolve_client
        _, selected = resolve_client()
        return "ok", f"目标客户端 {selected} 的 provides 摘要校验通过"

    add("client_profile", client, "检查 client_profiles.json 的默认档案及 provides 摘要")

    def apks():
        from .delivery_safety import resolve_apks
        files = resolve_apks(None)
        missing = sum(not p.is_file() for p in files)
        return ("ok" if files and not missing else "fail",
                f"client_apks: 配置 {len(files)} 个，缺少 {missing} 个" +
                ("；未配置会跳过撞名检查" if not files else "；这里只检查存在性，不证明 APK 身份"))

    add("client_apks", apks, "在本机 profile 的 client_apks.<档案名> 配置 APK 路径列表；勿提交 APK")

    def rehearsal():
        from .rehearsal_io import configured_server, server_root
        name = configured_server()
        if name is None:
            return "warn", "未配置预演服务器；预演不可用"
        root = server_root(name)
        ok = root.is_dir() and (root / "assets/asset-patch/manifest.json").is_file()
        return "ok" if ok else "fail", "预演服务器目录和 manifest 存在" if ok else "预演服务器目录或 manifest 缺失"

    add("rehearsal", rehearsal, "配置 rehearsal_server 与 servers.<名称>.root；只检查本地镜像，不连接服务器")
    if fast:
        if source is not None:
            chain = getattr(source, "chain", None)
            missing = len(chain.missing) if chain else 0
            add("patch_chain", lambda: ("fail" if missing else "ok", f"已加载视图缺 {missing} 个 ZIP；未重新扫描"),
                "补齐 ZIP 后重启；运行 doctor 做完整文件检查")
        else:
            add("patch_chain", lambda: ("warn", "快速体检未扫描补丁目录"), "运行 python -m wf.studio doctor")
    else:
        add("patch_chain", chain_check, "补齐配置搜索目录内缺少的 ZIP，修正 manifest 依赖链；不自动下载")


def chain_check():
    from wf.view.config import view_config, view_options
    from wf.view.chain import manifest_tip, resolve_chain
    from wf.view.archive_index import index_zip_names
    from .source import default_chain_settings
    selected, options = view_options()
    manifest, directories = (None, None) if selected else default_chain_settings()
    _, manifest, directories, extras = view_config(manifest=options.get("manifest") or manifest,
        search_dirs=options.get("zip_dirs") if selected else directories,
        manifests=options.get("manifests"), view_name=selected)
    base = options.get("base_version", "1.4.131")
    tip = options.get("tip") or manifest_tip(manifest, directories, base, extras)
    edges = resolve_chain(manifest, directories, base, tip, extras)
    wanted = {name for edge in edges for name in edge["names"]}
    found = index_zip_names(directories, wanted)
    missing = sorted(wanted - found.keys())
    return ("fail" if missing else "ok", f"补丁链 {tip}: 需要 {len(wanted)} 个 ZIP，缺 {len(missing)} 个" +
            ("：" + ", ".join(missing) if missing else "；仅检查存在性，启动时校验摘要"))
