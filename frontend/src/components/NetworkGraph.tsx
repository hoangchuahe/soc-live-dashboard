import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { NetworkNode, NetworkEdge } from '../types'

interface Props {
  nodes: NetworkNode[]
  edges: NetworkEdge[]
}

const NODE_COLOR: Record<string, string> = {
  firewall:    '#f97316',
  switch:      '#3b82f6',
  server:      '#06b6d4',
  workstation: '#22c55e',
  external:    '#ef4444',
}

const NODE_ICON: Record<string, string> = {
  firewall:    '🔥',
  switch:      '🔀',
  server:      '🖥',
  workstation: '💻',
  external:    '🌐',
}

interface SimNode extends NetworkNode {
  x?: number
  y?: number
  fx?: number | null
  fy?: number | null
}

interface SimEdge {
  source: SimNode | string
  target: SimNode | string
}

export function NetworkGraph({ nodes, edges }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return

    const rect = svgRef.current.getBoundingClientRect()
    const W = rect.width
    const H = rect.height

    const simNodes: SimNode[] = nodes.map(n => ({ ...n }))
    const simEdges: SimEdge[] = edges.map(e => ({ source: e.source, target: e.target }))

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    // Arrow marker
    svg.append('defs').append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 22)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#334155')

    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 4])
      .on('zoom', e => g.attr('transform', e.transform))
    svg.call(zoom)

    const g = svg.append('g')

    const simulation = d3.forceSimulation<SimNode>(simNodes)
      .force('link', d3.forceLink<SimNode, SimEdge>(simEdges).id(d => d.id).distance(90))
      .force('charge', d3.forceManyBody<SimNode>().strength(-280))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide<SimNode>(32))

    const link = g.append('g').selectAll<SVGLineElement, SimEdge>('line')
      .data(simEdges)
      .join('line')
      .attr('stroke', '#1e293b')
      .attr('stroke-width', 1.5)
      .attr('marker-end', 'url(#arrow)')

    const node = g.append('g').selectAll<SVGGElement, SimNode>('g')
      .data(simNodes)
      .join('g')
      .style('cursor', 'grab')
      .call(
        d3.drag<SVGGElement, SimNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart()
            d.fx = d.x; d.fy = d.y
          })
          .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0)
            d.fx = null; d.fy = null
          }),
      )

    // Risk ring (pulses for high-risk)
    node.append('circle')
      .attr('r', d => 14 + d.risk * 10)
      .attr('fill', 'none')
      .attr('stroke', d => d.risk > 0.7 ? '#ef4444' : d.risk > 0.4 ? '#f97316' : '#22c55e')
      .attr('stroke-width', 1.5)
      .attr('opacity', 0.5)
      .attr('class', d => d.risk > 0.7 ? 'pulse-ring' : '')

    // Main circle
    node.append('circle')
      .attr('r', 14)
      .attr('fill', d => NODE_COLOR[d.type] ?? '#64748b')
      .attr('fill-opacity', 0.15)
      .attr('stroke', d => NODE_COLOR[d.type] ?? '#64748b')
      .attr('stroke-width', 1.5)

    // Icon
    node.append('text')
      .text(d => NODE_ICON[d.type] ?? '●')
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'central')
      .style('font-size', '12px')
      .style('user-select', 'none')

    // Label
    node.append('text')
      .text(d => d.label)
      .attr('y', 26)
      .attr('text-anchor', 'middle')
      .style('fill', '#94a3b8')
      .style('font-size', '9px')
      .style('user-select', 'none')

    // Risk % label
    node.append('text')
      .text(d => `${Math.round(d.risk * 100)}%`)
      .attr('y', 36)
      .attr('text-anchor', 'middle')
      .style('fill', d => d.risk > 0.7 ? '#ef4444' : d.risk > 0.4 ? '#f97316' : '#22c55e')
      .style('font-size', '8px')
      .style('user-select', 'none')

    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as SimNode).x ?? 0)
        .attr('y1', d => (d.source as SimNode).y ?? 0)
        .attr('x2', d => (d.target as SimNode).x ?? 0)
        .attr('y2', d => (d.target as SimNode).y ?? 0)

      node.attr('transform', d => `translate(${d.x ?? 0},${d.y ?? 0})`)
    })

    return () => { simulation.stop() }
  }, [nodes, edges])

  return (
    <div className="relative w-full h-full">
      <div className="absolute bottom-3 left-4 flex flex-wrap gap-3 text-xs text-slate-500">
        {Object.entries(NODE_COLOR).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full inline-block" style={{ backgroundColor: color }} />
            {type}
          </span>
        ))}
      </div>
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  )
}
