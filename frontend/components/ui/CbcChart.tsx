"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  ResponsiveContainer,
  ReferenceLine,
  LabelList,
} from "recharts";

interface ParamData {
  value: number | string;
  unit: string;
  status: "normal" | "high" | "low";
  reference?: { low: number; high: number };
}

interface CbcChartProps {
  data: Record<string, ParamData>;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function barColor(status: string): string {
  if (status === "high") return "#ef4444";
  if (status === "low")  return "#eab308";
  return "#22c55e";
}

function barBg(status: string): string {
  if (status === "high") return "rgba(239,68,68,0.08)";
  if (status === "low")  return "rgba(234,179,8,0.08)";
  return "rgba(34,197,94,0.08)";
}

/** Express `value` as a percentage of the reference midpoint (100 = midpoint) */
function toPercent(value: number, ref?: { low: number; high: number }): number {
  if (!ref || ref.low == null || ref.high == null) return 0;
  const mid = (ref.low + ref.high) / 2;
  if (mid === 0) return 0;
  return Math.round((value / mid) * 100);
}

/** Express reference boundary as percent of midpoint */
function boundPercent(bound: number, ref: { low: number; high: number }): number {
  const mid = (ref.low + ref.high) / 2;
  if (mid === 0) return 0;
  return Math.round((bound / mid) * 100);
}

// ─── Custom Tooltip ───────────────────────────────────────────────────────────

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-[#18181b] border border-white/10 rounded-xl p-3.5 shadow-2xl text-sm min-w-[170px]">
      <p className="font-bold text-white mb-2">{d.name}</p>
      <div className="space-y-1.5">
        <div className="flex justify-between gap-4">
          <span className="text-zinc-500">Value</span>
          <span className="font-semibold text-white">{d.rawValue} {d.unit}</span>
        </div>
        {d.refLow != null && (
          <div className="flex justify-between gap-4">
            <span className="text-zinc-500">Normal range</span>
            <span className="text-zinc-300">{d.refLow} – {d.refHigh} {d.unit}</span>
          </div>
        )}
        <div className="pt-1 border-t border-white/5">
          <span className={`text-xs font-bold capitalize ${
            d.status === "high" ? "text-red-400" :
            d.status === "low"  ? "text-yellow-400" :
                                  "text-green-400"
          }`}>
            {d.status === "normal" ? "Within normal range" : `${d.status} — outside normal range`}
          </span>
        </div>
      </div>
    </div>
  );
}

// ─── Custom label on top of bar ───────────────────────────────────────────────

function ValueLabel(props: any) {
  const { x, y, width, value, index, chartData } = props;
  if (value == null) return null;
  const d = chartData[index];
  if (!d) return null;

  const color = d.status === "high" ? "#f87171" : d.status === "low" ? "#facc15" : "#4ade80";

  return (
    <g>
      <text
        x={x + width / 2}
        y={y - 6}
        fill={color}
        textAnchor="middle"
        fontSize={10}
        fontWeight="600"
        fontFamily="'Inter', sans-serif"
      >
        {d.rawValue}
      </text>
      <text
        x={x + width / 2}
        y={y - 6 + 11}
        fill="#71717a"
        textAnchor="middle"
        fontSize={8.5}
        fontFamily="'Inter', sans-serif"
      >
        {d.unit}
      </text>
    </g>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export function CbcChart({ data }: CbcChartProps) {
  const chartData = Object.entries(data)
    .filter(([, d]) => {
      const v = typeof d.value === "string" ? parseFloat(d.value) : d.value;
      return !isNaN(v);
    })
    .map(([key, d]) => {
      const rawValue = typeof d.value === "string" ? parseFloat(d.value) : d.value;
      const pct = toPercent(rawValue, d.reference);
      const refLowPct  = d.reference ? boundPercent(d.reference.low,  d.reference) : null;
      const refHighPct = d.reference ? boundPercent(d.reference.high, d.reference) : null;
      return {
        name: key,
        pct,
        rawValue,
        unit: d.unit || "",
        status: d.status,
        refLow:    d.reference?.low  ?? null,
        refHigh:   d.reference?.high ?? null,
        refLowPct,
        refHighPct,
      };
    });

  if (chartData.length === 0) {
    return <p className="text-zinc-500 text-sm text-center py-8">No numeric parameters to display.</p>;
  }

  const abnormal = chartData.filter((d) => d.status !== "normal");
  const normal   = chartData.filter((d) => d.status === "normal");

  return (
    <div>
      {/* ── Summary row ── */}
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <div className="flex items-center gap-2 text-sm">
          <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
          <span className="text-zinc-400">Normal <span className="font-bold text-white">{normal.length}</span></span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <div className="w-2.5 h-2.5 rounded-full bg-yellow-500" />
          <span className="text-zinc-400">Low <span className="font-bold text-white">{chartData.filter(d => d.status === "low").length}</span></span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
          <span className="text-zinc-400">High <span className="font-bold text-white">{chartData.filter(d => d.status === "high").length}</span></span>
        </div>
        <span className="ml-auto text-xs text-zinc-600">Bar height = % of normal midpoint · 100% = exact midpoint</span>
      </div>

      {/* ── Bar chart ── */}
      <ResponsiveContainer width="100%" height={340}>
        <BarChart
          data={chartData}
          margin={{ top: 28, right: 16, left: 0, bottom: 64 }}
          barCategoryGap="28%"
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke="rgba(255,255,255,0.04)"
            vertical={false}
          />

          {/* Normal zone: 80%–120% of midpoint is a reasonable approximation */}
          <ReferenceLine
            y={100}
            stroke="rgba(255,255,255,0.20)"
            strokeDasharray="6 3"
            label={{
              value: "Midpoint (100%)",
              position: "insideTopRight",
              fill: "#52525b",
              fontSize: 10,
              fontFamily: "Inter",
            }}
          />
          <ReferenceLine
            y={80}
            stroke="rgba(234,179,8,0.25)"
            strokeDasharray="4 4"
            label={{
              value: "−20%",
              position: "insideTopRight",
              fill: "#713f12",
              fontSize: 9,
              fontFamily: "Inter",
            }}
          />
          <ReferenceLine
            y={120}
            stroke="rgba(239,68,68,0.25)"
            strokeDasharray="4 4"
            label={{
              value: "+20%",
              position: "insideTopRight",
              fill: "#7f1d1d",
              fontSize: 9,
              fontFamily: "Inter",
            }}
          />

          <XAxis
            dataKey="name"
            tick={{ fill: "#71717a", fontSize: 11, fontFamily: "Inter" }}
            tickLine={false}
            axisLine={{ stroke: "rgba(255,255,255,0.05)" }}
            angle={-40}
            textAnchor="end"
            interval={0}
            height={64}
          />
          <YAxis
            tick={{ fill: "#71717a", fontSize: 11, fontFamily: "Inter" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${v}%`}
            domain={[0, "auto"]}
            width={40}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: "rgba(255,255,255,0.025)" }} />

          <Bar dataKey="pct" radius={[5, 5, 0, 0]} maxBarSize={44}>
            {/* Value + unit label on top of each bar */}
            <LabelList
              content={(props: any) => (
                <ValueLabel {...props} chartData={chartData} />
              )}
            />
            {chartData.map((entry) => (
              <Cell
                key={entry.name}
                fill={barColor(entry.status)}
                fillOpacity={entry.status === "normal" ? 0.75 : 0.9}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* ── Abnormal parameters detail ── */}
      {abnormal.length > 0 && (
        <div className="mt-6 pt-5 border-t border-white/5">
          <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">
            Out-of-range parameters
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {abnormal.map((d) => (
              <div
                key={d.name}
                className={`flex items-center justify-between gap-3 px-4 py-3 rounded-xl border text-sm
                  ${d.status === "high"
                    ? "bg-red-500/6 border-red-500/15"
                    : "bg-yellow-500/6 border-yellow-500/15"
                  }`}
              >
                <div>
                  <span className="font-semibold text-white">{d.name}</span>
                  {d.refLow != null && (
                    <span className="text-xs text-zinc-500 ml-2">
                      Ref: {d.refLow}–{d.refHigh} {d.unit}
                    </span>
                  )}
                </div>
                <div className="text-right flex-shrink-0">
                  <span className={`font-bold ${d.status === "high" ? "text-red-400" : "text-yellow-400"}`}>
                    {d.rawValue} {d.unit}
                  </span>
                  <span className={`ml-2 text-xs font-semibold capitalize ${d.status === "high" ? "text-red-500" : "text-yellow-500"}`}>
                    {d.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
