import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { EcsEvent } from '../types'
import { ecs } from '../types'

interface Props {
  events: EcsEvent[]
}

const SEV_COLOR: Record<string, string> = {
  low:      '#22c55e',
  medium:   '#eab308',
  high:     '#f97316',
  critical: '#ef4444',
}

const MARGIN = { top: 24, right: 16, bottom: 24, left: 16 }

export function EventTimeline({ events }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!svgRef.current || events.length === 0) return

    const rect = svgRef.current.getBoundingClientRect()
    const W = rect.width
    const H = rect.height
    const iW = W - MARGIN.left - MARGIN.right
    const midY = H / 2

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const times = events.map(e => new Date(e['@timestamp']).getTime())
    const extent = d3.extent(times) as [number, number]
    const xDomain: [number, number] = extent[0] === extent[1]
      ? [extent[0] - 60_000, extent[0] + 60_000]
      : extent

    const x = d3.scaleTime().domain(xDomain).range([MARGIN.left, MARGIN.left + iW])

    const g = svg.append('g')

    g.append('line')
      .attr('x1', MARGIN.left).attr('x2', MARGIN.left + iW)
      .attr('y1', midY).attr('y2', midY)
      .attr('stroke', '#1e293b').attr('stroke-width', 1)

    g.append('g')
      .attr('transform', `translate(0,${midY + 14})`)
      .call(d3.axisBottom(x).ticks(5).tickSize(0))
      .call(ax => { ax.select('.domain').remove() })
      .selectAll('text').style('fill', '#475569').style('font-size', '9px')

    const dot = g.selectAll<SVGCircleElement, EcsEvent>('circle')
      .data(events)
      .join('circle')
      .attr('cx', d => x(new Date(d['@timestamp'])))
      .attr('cy', d => ecs.isAlert(d) ? midY - 12 : midY)
      .attr('r', d => ecs.isAlert(d) ? 7 : 5)
      .attr('fill', d => SEV_COLOR[ecs.severity(d)] ?? '#64748b')
      .attr('stroke', d => ecs.isAlert(d) ? '#06b6d4' : '#0f172a')
      .attr('stroke-width', d => ecs.isAlert(d) ? 2 : 1.5)
      .style('cursor', 'pointer')

    const tooltip = d3.select(tooltipRef.current)

    dot
      .on('mouseenter', (event, d) => {
        tooltip
          .style('opacity', '1')
          .style('left', `${event.offsetX + 12}px`)
          .style('top', `${event.offsetY - 50}px`)
          .html(`
            <div class="text-xs font-bold text-slate-200">${d.rule?.name ?? ecs.type(d)}</div>
            <div class="text-xs text-slate-400">${ecs.source(d)} · ${ecs.country(d)}</div>
            <div class="text-xs text-slate-500">${d.message}</div>
            ${ecs.technique(d) ? `<div class="text-[10px] text-purple-400 mt-1">${ecs.technique(d)} · ${ecs.tactic(d) ?? ''}</div>` : ''}
          `)
      })
      .on('mouseleave', () => tooltip.style('opacity', '0'))

    const legend = g.append('g').attr('transform', `translate(${MARGIN.left},8)`)
    Object.entries(SEV_COLOR).forEach(([sev, color], i) => {
      const grp = legend.append('g').attr('transform', `translate(${i * 72},0)`)
      grp.append('circle').attr('r', 4).attr('fill', color)
      grp.append('text').attr('x', 8).attr('dominant-baseline', 'central')
        .style('fill', '#64748b').style('font-size', '9px').text(sev)
    })
    // Alert legend
    const alertLeg = legend.append('g').attr('transform', `translate(${4 * 72 + 16},0)`)
    alertLeg.append('circle').attr('r', 5).attr('fill', '#ef4444').attr('stroke', '#06b6d4').attr('stroke-width', 2)
    alertLeg.append('text').attr('x', 10).attr('dominant-baseline', 'central')
      .style('fill', '#06b6d4').style('font-size', '9px').text('alert (rule fired)')
  }, [events])

  return (
    <div className="relative w-full h-full">
      <svg ref={svgRef} className="w-full h-full" />
      <div
        ref={tooltipRef}
        className="absolute pointer-events-none bg-slate-800 border border-slate-700 rounded px-3 py-2 opacity-0 transition-opacity max-w-xs z-20"
        style={{ top: 0, left: 0 }}
      />
    </div>
  )
}
