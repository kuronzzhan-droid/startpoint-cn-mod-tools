"""Parser registration for host-local target commands."""

from __future__ import annotations

from typing import Mapping


def add_target_commands(commands, context, handlers: Mapping[str, object]) -> None:
    bootstrap = commands.add_parser(
        "bootstrap", help="初始化已停止的首个受管 baseline", output_context=context
    )
    bootstrap.add_argument("--target", required=True)
    bootstrap.add_argument(
        "--confirm", required=True, choices=("BOOTSTRAP_WF_TARGET",)
    )
    bootstrap.set_defaults(handler=handlers["bootstrap"])

    resume = commands.add_parser(
        "resume", help="恢复已停止的受管目标服务", output_context=context
    )
    resume.add_argument("--target", required=True)
    resume.add_argument(
        "--confirm", required=True, choices=("RESUME_WF_TARGET",)
    )
    resume.set_defaults(handler=handlers["resume"])

    capture = commands.add_parser(
        "capture-requirements", help="从当前目标只读捕获发行要求", output_context=context
    )
    capture.add_argument("--target", required=True)
    capture.add_argument("--workspace", required=True)
    capture.add_argument("--output", required=True)
    capture.add_argument("--json", action="store_true", required=True)
    capture.set_defaults(handler=handlers["capture"])

    plan = commands.add_parser(
        "plan-install", help="只读预览兼容性、冲突与回退", output_context=context
    )
    plan.add_argument("--target", required=True)
    plan.add_argument("--release", required=True)
    plan.add_argument("--json", action="store_true", required=True)
    plan.set_defaults(handler=handlers["plan"])

    probe = commands.add_parser(
        "probe", help="读取受管目标事实", output_context=context
    )
    probe.add_argument("--target", required=True)
    probe.add_argument("--json", action="store_true", required=True)
    probe.set_defaults(handler=handlers["probe"])

    install = commands.add_parser(
        "install", help="安装已验证的本地发行物", output_context=context
    )
    install.add_argument("--target", required=True)
    install.add_argument("--release", required=True)
    install.add_argument("--confirm", required=True, choices=("INSTALL_WF_RELEASE",))
    install.set_defaults(handler=handlers["install"])

    legacy = commands.add_parser(
        "install-legacy", help="安装到已证明的 transition 旧服目标", output_context=context
    )
    legacy.add_argument("--target", required=True)
    legacy.add_argument("--release", required=True)
    legacy.add_argument("--confirm", required=True, choices=("INSTALL_LEGACY_RELEASE",))
    legacy.set_defaults(handler=handlers["legacy"])

    legacy_rollback = commands.add_parser(
        "rollback-legacy", help="回到 transition 旧服的前一条 CDN 链尾", output_context=context
    )
    legacy_rollback.add_argument("--target", required=True)
    legacy_rollback.add_argument("--to-release", dest="to_release", required=True)
    legacy_rollback.add_argument(
        "--confirm", required=True, choices=("ROLLBACK_LEGACY_RELEASE",)
    )
    legacy_rollback.set_defaults(handler=handlers["legacy_rollback"])

    rollback = commands.add_parser(
        "rollback", help="恢复失败事务或显式回到 previous 状态", output_context=context
    )
    rollback.add_argument("--target", required=True)
    rollback_mode = rollback.add_mutually_exclusive_group(required=True)
    rollback_mode.add_argument("--operation")
    rollback_mode.add_argument("--to-release", dest="to_release")
    rollback.add_argument(
        "--confirm",
        required=True,
        choices=("RECOVER_FAILED_INSTALL", "I_UNDERSTAND_DATA_DOWNGRADE_RISK"),
    )
    rollback.set_defaults(handler=handlers["rollback"])


__all__ = ["add_target_commands"]
