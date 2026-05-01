import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { MetricPoint } from '../types'

interface Props {
  data: MetricPoint[]
}

const MARGIN = { top: 16, right: 16, bottom: 28, left: 44 }

export function MetricsChart({ data }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current || data.length < 2) return

    const rect = svgRef.current.getBoundingClientRect()
    const W = rect.width
    const H = rect.height
    const iW = W - MARGIN.left - MARGIN.right
    const iH = H - MARGIN.top - MARGIN.bottom

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const defs = svg.append('defs')

    const mkGrad = (id: string, color: string) => {
      const g = defs.append('linearGradient').attr('id', id).attr('x1', 0).attr('y1', 0).attr('x2', 0).attr('y2', 1)
      g.append('stop').attr('offset', '0%').style('stop-color', color).style('stop-opacity', 0.35)
      g.append('stop').attr('offset', '100%').style('stop-color', color).style('stop-opacity', 0)
    }
    mkGrad('grad-cpu', '#06b6d4')
    mkGrad('grad-mem', '#a855f7')

    const x = d3.scaleLinear().domain([0, data.length - 1]).range([0, iW])
    const y = d3.scaleLinear().domain([0, 100]).range([iH, 0])

    const g = svg.append('g').attr('transform', `translate(${MARGIN.left},${MARGIN.top})`)

    // Grid lines
    g.append('g')
      .selectAll('line')
      .data(y.ticks(5))
      .join('line')
      .attr('x1', 0).attr('x2', iW)
      .attr('y1', d => y(d)).attr('y2', d => y(d))
      .attr('stroke', '#1e293b').attr('stroke-dasharray', '3,3')

    // Axes
    g.append('g')
      .attr('transform', `translate(0,${iH})`)
      .call(d3.axisBottom(x).ticks(6).tickFormat(d => `${-Math.round((data.length - 1 - Number(d)))}s`))
      .call(ax => { ax.select('.domain').remove(); ax.selectAll('line').remove() })
      .selectAll('text').style('fill', '#475569').style('font-size', '10px')

    g.append('g')
      .call(d3.axisLeft(y).ticks(5).tickFormat(d => `${d}%`))
      .call(ax => { ax.select('.domain').remove(); ax.selectAll('line').remove() })
      .selectAll('text').style('fill', '#475569').style('font-size', '10px')

    const mkArea = (accessor: (d: MetricPoint) => number) =>
      d3.area<MetricPoint>().x((_, i) => x(i)).y0(iH).y1(d => y(accessor(d))).curve(d3.curveCatmullRom)

    const mkLine = (accessor: (d: MetricPoint) => number) =>
      d3.line<MetricPoint>().x((_, i) => x(i)).y(d => y(accessor(d))).curve(d3.curveCatmullRom)

    // Areas
    g.append('path').datum(data).attr('fill', 'url(#grad-cpu)').attr('d', mkArea(d => d.cpu))
    g.append('path').datum(data).attr('fill', 'url(#grad-mem)').attr('d', mkArea(d => d.memory))

    // Lines
    g.append('path').datum(data).attr('fill', 'none').attr('stroke', '#06b6d4').attr('stroke-width', 1.5).attr('d', mkLine(d => d.cpu))
    g.append('path').datum(data).attr('fill', 'none').attr('stroke', '#a855f7').attr('stroke-width', 1.5).attr('d', mkLine(d => d.memory))

    // End dots
    const last = data[data.length - 1]
    const endX = x(data.length - 1)
    ;[{ val: last.cpu, color: '#06b6d4' }, { val: last.memory, color: '#a855f7' }].forEach(({ val, color }) => {
      g.append('circle').attr('cx', endX).attr('cy', y(val)).attr('r', 3).attr('fill', color)
      g.append('circle').attr('cx', endX).attr('cy', y(val)).attr('r', 6)
        .attr('fill', 'none').attr('stroke', color).attr('stroke-width', 1).attr('opacity', 0.4)
    })
  }, [data])

  return (
    <div className="relative w-full h-full">
      <div className="absolute top-3 right-4 flex gap-4 text-xs">
        <span className="flex items-center gap-1.5 text-cyan-400"><span className="w-3 h-0.5 bg-cyan-400 inline-block" />CPU</span>
        <span className="flex items-center gap-1.5 text-purple-400"><span className="w-3 h-0.5 bg-purple-400 inline-block" />Memory</span>
      </div>
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  )
}
