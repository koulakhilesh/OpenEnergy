import { useEffect, useRef } from "react";
import type { Data, Layout, PlotMouseEvent } from "plotly.js";

const LAYOUT: Partial<Layout> = {
  template: undefined,
  legend: { orientation: "h", y: -0.2 },
  margin: { l: 60, r: 20, t: 50, b: 40 },
  height: 380,
  paper_bgcolor: "#fff",
  plot_bgcolor: "#fff",
  xaxis: { gridcolor: "#ebf0f8", zeroline: false },
  yaxis: { gridcolor: "#ebf0f8", zerolinecolor: "#ebf0f8" },
  font: { family: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif", color: "#1f2933" },
};

interface Props {
  data: Data[];
  title: string;
  xTitle?: string;
  yTitle: string;
  layout?: Partial<Layout>;
  /** Called with the clicked point's ``customdata`` (bars open their result). */
  onClick?: (customdata: unknown) => void;
}

/** A plotly chart; plotly is loaded on first use so pages without charts stay small. */
export function Plot({ data, title, xTitle, yTitle, layout, onClick }: Props) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let cancelled = false;
    const node = box.current;
    import("plotly.js-basic-dist-min").then(({ default: Plotly }) => {
      if (cancelled || !node) return;
      const full: Partial<Layout> = {
        ...LAYOUT,
        title: { text: title },
        xaxis: { ...LAYOUT.xaxis, title: { text: xTitle ?? "" } },
        yaxis: { ...LAYOUT.yaxis, title: { text: yTitle } },
        ...layout,
      };
      Plotly.react(node, data, full, { displaylogo: false, responsive: true }).then(() => {
        if (!onClick) return;
        const plot = node as unknown as { removeAllListeners?: (e: string) => void } & {
          on: (event: string, handler: (e: PlotMouseEvent) => void) => void;
        };
        plot.removeAllListeners?.("plotly_click");
        plot.on("plotly_click", (event) => onClick(event.points[0]?.customdata));
      });
    });
    return () => {
      cancelled = true;
    };
  }, [data, title, xTitle, yTitle, layout, onClick]);
  return <div ref={box} className="plot" role="img" aria-label={title} />;
}
