const PLANNED: { title: string; body: string }[] = [
  { title: "Boss 总览", body: "主线、领主战、共同决战、五重、深渊、木人：按模式列出现有 boss 和它们的副本。" },
  { title: "副本模板", body: "从「领主战 5 档」「共同决战」「五重」等模板新建，自动填 quest、zone、波次。" },
  { title: "行为 / 出招", body: "esdl 时间线编辑，出招用 marker 点；六件逐字节往返。" },
  { title: "场地与站位", body: "地形层数 = 波数；多波必须填 c7/c8；p1/p2/p3 站位按母本对齐。" },
  { title: "难度与机制", body: "试炼击破条、免伤链接、阶段转场（quest 阶段链）、场地效果。" },
  { title: "商店与武器", body: "领主币或魂珠商店、每个 boss 两把武器、横幅和页头。" },
  { title: "美术", body: "boss 场景、活动页、商店横幅、币和武器图标。" },
  { title: "预检", body: "等级缺口、属性替换的预载垫片、三人房图集余量。" },
];

export function BossPlaceholder() {
  return (
    <section class="page">
      <div class="page-head">
        <div>
          <h1>BOSS工坊</h1>
          <p class="muted">尚未开工。本页只列出计划中的页面，没有读取或修改任何 boss 数据。</p>
        </div>
        <span class="pill">规划中</span>
      </div>
      <ul class="planned">
        {PLANNED.map((p) => (
          <li>
            <h3>{p.title}</h3>
            <p class="muted">{p.body}</p>
            <span class="state-none small">未接入</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
