import { useEffect, useRef } from 'react'
import * as d3 from 'd3'
import type { Bucket } from '../../lib/histogram'

export function EventHistogram({ buckets }: { buckets: Bucket[] }) {
  const ref = useRef<SVGSVGElement | null>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const svg = d3.select(el)
    svg.selectAll('*').remove()

    const width = el.clientWidth || 600
    const height = 120
    const m = { top: 8, right: 8, bottom: 4, left: 28 }
    const iw = Math.max(1, width - m.left - m.right)
    const ih = Math.max(1, height - m.top - m.bottom)

    const g = svg.append('g').attr('transform', `translate(${m.left},${m.top})`)
    const x = d3.scaleBand<number>().domain(buckets.map((_, i) => i)).range([0, iw]).padding(0.15)
    const maxCount = d3.max(buckets, b => b.count) ?? 0
    const y = d3.scaleLinear().domain([0, Math.max(1, maxCount)]).range([ih, 0])

    g.append('g').attr('class', 'axis')
      .call(d3.axisLeft(y).ticks(3).tickSize(-iw))
      .selectAll('text').attr('fill', '#64748b').attr('font-size', 9)

    g.selectAll('rect.bar').data(buckets).join('rect')
      .attr('class', 'bar')
      .attr('x', (_, i) => x(i) ?? 0)
      .attr('y', b => y(b.count))
      .attr('width', x.bandwidth())
      .attr('height', b => ih - y(b.count))
      .attr('fill', '#06b6d4')
      .attr('opacity', 0.85)
  }, [buckets])

  return <svg ref={ref} className="w-full" style={{ height: 120 }} />
}
