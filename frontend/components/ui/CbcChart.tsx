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
import { useTheme } from "./ThemeProvider";

interface ParamData {
  value: number | string;
  unit: string;
  status: "normal" | "high" | "low";
  reference?: { low: number; high: number };
}

interface CbcChartProps {
  data: Record<string, ParamData>;
}

function barColor(status: string): string {
  if (status === "high") return "#ef4444";
  if (status === "low") return "#eab308";
  return "#22c55e";
}

function toPercent(value: number, ref?: { low: number; high: number }): number {
  if (!ref || ref.low == null || ref.high == null) return 0;
  const mid = (ref.low + ref.high) / 2;
  if (mid === 0) return 0;
  return Math.round((value / mid) * 100);
}

function CustomTooltip({ active, payload, isDark }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;

  return (
    <div
      className="rounded-xl p-3.5 shadow-2xl text-sm min-w-[170px]"
      style={{
        background: isDark ? "rgba(6,20,38,0.96)" : "#ffffff",
        border: isDark ? "1px solid rgba(144,224,239,0.14)" : "1px solid rgba(226,232,240,1)",
      }}
    >
      <p className="font-bold text-slate-900 mb-2">{d.name}</p>
      <div className="space-y-1.5">
        <div className="flex justify-between gap-4">
          <span className="text-zinc-500">Value</span>
          <span className="font-semibold text-slate-900">
            {d.rawValue} {d.unit}
          </span>
        </div>
        {d.refLow != null && (
          <div className="flex justify-between gap-4">
            <span className="text-zinc-500">Normal range</span>
            <span className="text-slate-700">
              {d.refLow} - {d.refHigh} {d.unit}
            </span>
          </div>
        )}
        <div className="pt-1 border-t border-white/5">
          <span
            className={`text-xs font-bold capitalize ${
              d.status === "high"
                ? "text-red-400"
                : d.status === "low"
                  ? "text-yellow-400"
                  : "text-green-400"
            }`}
          >
            {d.status === "normal" ? "Within normal range" : `${d.status} - outside normal range`}
          </span>
        </div>
      </div>
    </div>
  );
}

function ValueLabel(props: any) {
  const { x, y, width, value, index, chartData, isDark } = props;
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
        y={y + 5}
        fill={isDark ? "#9cc8d8" : "#64748b"}
        textAnchor="middle"
        fontSize={8.5}
        fontFamily="'Inter', sans-serif"
      >
        {d.unit}
      </text>
    </g>
  );
}

export function CbcChart({ data }: CbcChartProps) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

  const chartData = Object.entries(data)
    .filter(([, d]) => {
      const v = typeof d.value === "string" ? parseFloat(d.value) : d.value;
      return !isNaN(v);
    })
    .map(([key, d]) => {
      const rawValue = typeof d.value === "string" ? parseFloat(d.value) : d.value;
      return {
        name: key,
        pct: toPercent(rawValue, d.reference),
        rawValue,
        unit: d.unit || "",
        status: d.status,
        refLow: d.reference?.low ?? null,
        refHigh: d.reference?.high ?? null,
      };
    });

  if (chartData.length === 0) {
    return <p className="text-zinc-500 text-sm text-center py-8">No numeric parameters to display.</p>;
  }

  const abnormal = chartData.filter((d) => d.status !== "normal");
  const normal = chartData.filter((d) => d.status === "normal");

  return (
    <div>
      <div className="flex items-center gap-4 mb-6 flex-wrap">
        <div className="flex items-center gap-2 text-sm">
          <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
          <span className="text-zinc-400">
            Normal <span className="font-bold text-slate-900">{normal.length}</span>
          </span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <div className="w-2.5 h-2.5 rounded-full bg-yellow-500" />
          <span className="text-zinc-400">
            Low <span className="font-bold text-slate-900">{chartData.filter((d) => d.status === "low").length}</span>
          </span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
          <span className="text-zinc-400">
            High <span className="font-bold text-slate-900">{chartData.filter((d) => d.status === "high").length}</span>
          </span>
        </div>
        <span className="ml-auto text-xs text-zinc-600">Bar height = % of normal midpoint. 100% = exact midpoint</span>
      </div>

      <ResponsiveContainer width="100%" height={340}>
        <BarChart data={chartData} margin={{ top: 28, right: 16, left: 0, bottom: 64 }} barCategoryGap="28%">
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={isDark ? "rgba(144,224,239,0.14)" : "rgba(148,163,184,0.18)"}
            vertical={false}
          />

          <ReferenceLine
            y={100}
            stroke={isDark ? "rgba(144,224,239,0.24)" : "rgba(148,163,184,0.38)"}
            strokeDasharray="6 3"
            label={{
              value: "Midpoint (100%)",
              position: "insideTopRight",
              fill: isDark ? "#9cc8d8" : "#64748b",
              fontSize: 10,
              fontFamily: "Inter",
            }}
          />
          <ReferenceLine
            y={80}
            stroke={isDark ? "rgba(250,204,21,0.28)" : "rgba(234,179,8,0.25)"}
            strokeDasharray="4 4"
            label={{
              value: "-20%",
              position: "insideTopRight",
              fill: isDark ? "#fde68a" : "#713f12",
              fontSize: 9,
              fontFamily: "Inter",
            }}
          />
          <ReferenceLine
            y={120}
            stroke={isDark ? "rgba(248,113,113,0.28)" : "rgba(239,68,68,0.25)"}
            strokeDasharray="4 4"
            label={{
              value: "+20%",
              position: "insideTopRight",
              fill: isDark ? "#fecaca" : "#7f1d1d",
              fontSize: 9,
              fontFamily: "Inter",
            }}
          />

          <XAxis
            dataKey="name"
            tick={{ fill: isDark ? "#b8dce8" : "#71717a", fontSize: 11, fontFamily: "Inter" }}
            tickLine={false}
            axisLine={{ stroke: isDark ? "rgba(144,224,239,0.16)" : "rgba(148,163,184,0.22)" }}
            angle={-40}
            textAnchor="end"
            interval={0}
            height={64}
          />
          <YAxis
            tick={{ fill: isDark ? "#b8dce8" : "#71717a", fontSize: 11, fontFamily: "Inter" }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `${v}%`}
            domain={[0, "auto"]}
            width={40}
          />
          <Tooltip
            content={<CustomTooltip isDark={isDark} />}
            cursor={{ fill: isDark ? "rgba(144,224,239,0.1)" : "rgba(226,232,240,0.45)" }}
          />

          <Bar dataKey="pct" radius={[5, 5, 0, 0]} maxBarSize={44}>
            <LabelList content={(props: any) => <ValueLabel {...props} chartData={chartData} isDark={isDark} />} />
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

      {abnormal.length > 0 && (
        <div className="mt-6 pt-5 border-t border-white/5">
          <p className="text-xs font-semibold text-zinc-500 uppercase tracking-widest mb-3">
            Out-of-range parameters
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {abnormal.map((d) => (
              <div
                key={d.name}
                className={`flex items-center justify-between gap-3 px-4 py-3 rounded-xl border text-sm ${
                  d.status === "high" ? "bg-red-500/6 border-red-500/15" : "bg-yellow-500/6 border-yellow-500/15"
                }`}
              >
                <div>
                  <span className="font-semibold text-slate-900">{d.name}</span>
                  {d.refLow != null && (
                    <span className="text-xs text-zinc-500 ml-2">
                      Ref: {d.refLow}-{d.refHigh} {d.unit}
                    </span>
                  )}
                </div>
                <div className="text-right flex-shrink-0">
                  <span className={`font-bold ${d.status === "high" ? "text-red-400" : "text-yellow-400"}`}>
                    {d.rawValue} {d.unit}
                  </span>
                  <span
                    className={`ml-2 text-xs font-semibold capitalize ${
                      d.status === "high" ? "text-red-500" : "text-yellow-500"
                    }`}
                  >
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
