import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import * as topojson from 'topojson-client'
import type { AttackArc } from '../types'
import type { Topology } from 'topojson-specification'

interface Props {
  arcs: AttackArc[]
}

// Ho Chi Minh City — the "defended" SOC location
const TARGET: [number, number] = [106.66, 10.82]

const SEV_COLOR: Record<string, string> = {
  low:      '#22c55e',
  medium:   '#eab308',
  high:     '#f97316',
  critical: '#ef4444',
}

export function GeoMap({ arcs }: Props) {
  const svgRef = useRef<SVGSVGElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [world, setWorld] = useState<Topology | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
      .then(r => r.json())
      .then(data => { setWorld(data); setLoading(false) })
      .catch(() => { setError(true); setLoading(false) })
  }, [])

  useEffect(() => {
    if (!svgRef.current || !world) return

    const rect = svgRef.current.getBoundingClientRect()
    const W = rect.width || 600
    const H = rect.height || 300

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    const projection = d3.geoNaturalEarth1()
      .scale(W / 6.4)
      .translate([W / 2, H / 2])

    const path = d3.geoPath().projection(projection)

    const g = svg.append('g')

    // Zoom + pan
    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.5, 8])
        .on('zoom', e => g.attr('transform', e.transform)),
    )

    // Ocean background
    g.append('path')
      .datum({ type: 'Sphere' } as d3.GeoPermissibleObjects)
      .attr('d', path)
      .attr('fill', '#0c1928')

    // Graticule
    g.append('path')
      .datum(d3.geoGraticule()())
      .attr('d', path)
      .attr('fill', 'none')
      .attr('stroke', '#0f2133')
      .attr('stroke-width', 0.4)

    // Countries — colour by attack count
    const countByCountry: Record<string, number> = {}
    for (const a of arcs) {
      countByCountry[a.country] = (countByCountry[a.country] ?? 0) + a.count
    }
    const maxCount = Math.max(...Object.values(countByCountry), 1)
    const colorScale = d3.scaleSequential(d3.interpolate('#0f2133', '#7f1d1d')).domain([0, maxCount])

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const countries = topojson.feature(world, (world as any).objects.countries) as d3.ExtendedFeatureCollection
    g.append('g').selectAll('path')
      .data(countries.features)
      .join('path')
      .attr('d', path as d3.ValueFn<SVGPathElement, d3.ExtendedFeature, string | null>)
      .attr('fill', '#0f2133')
      .attr('stroke', '#1e3a5f')
      .attr('stroke-width', 0.5)

    // ── Attack arcs ────────────────────────────────────────────────────────
    const targetXY = projection(TARGET)
    if (!targetXY) return

    // Aggregate arcs by country
    const byCountry: Record<string, AttackArc> = {}
    for (const a of arcs) {
      if (!byCountry[a.country] || a.count > byCountry[a.country].count) {
        byCountry[a.country] = a
      }
    }

    Object.values(byCountry).forEach(arc => {
      const srcXY = projection([arc.lng, arc.lat])
      if (!srcXY) return

      const color = SEV_COLOR[arc.severity] ?? '#64748b'

      // Great-circle arc
      g.append('path')
        .datum({
          type: 'LineString',
          coordinates: [[arc.lng, arc.lat], TARGET],
        } as d3.GeoPermissibleObjects)
        .attr('d', path)
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 0.8)
        .attr('stroke-dasharray', '3,4')
        .attr('opacity', 0.55)

      // Source pulse
      g.append('circle')
        .attr('cx', srcXY[0]).attr('cy', srcXY[1])
        .attr('r', 2 + Math.min(arc.count / 15, 4))
        .attr('fill', color)
        .attr('opacity', 0.9)

      // Outer ring
      g.append('circle')
        .attr('cx', srcXY[0]).attr('cy', srcXY[1])
        .attr('r', 5 + Math.min(arc.count / 15, 4))
        .attr('fill', 'none')
        .attr('stroke', color)
        .attr('stroke-width', 0.8)
        .attr('opacity', 0.3)

      // Country label for significant sources
      if (arc.count > 5) {
        g.append('text')
          .attr('x', srcXY[0] + 7)
          .attr('y', srcXY[1] + 3)
          .style('fill', color)
          .style('font-size', '8px')
          .style('user-select', 'none')
          .text(arc.country)
      }
    })

    // ── Target marker (HCMC / SOC) ─────────────────────────────────────────
    ;[12, 7, 3].forEach((r, i) => {
      g.append('circle')
        .attr('cx', targetXY[0]).attr('cy', targetXY[1])
        .attr('r', r)
        .attr('fill', i === 2 ? '#06b6d4' : 'none')
        .attr('stroke', '#06b6d4')
        .attr('stroke-width', i === 2 ? 0 : 1)
        .attr('opacity', i === 0 ? 0.2 : i === 1 ? 0.5 : 1)
    })
    g.append('text')
      .attr('x', targetXY[0] + 7)
      .attr('y', targetXY[1] + 3)
      .style('fill', '#06b6d4')
      .style('font-size', '8px')
      .style('user-select', 'none')
      .text('SOC ▸ HCMC')

  }, [world, arcs])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500 text-sm">
        Loading world map…
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-slate-600 text-xs text-center p-4">
        Map unavailable (offline)<br />Attack arcs will render when connected
      </div>
    )
  }

  return (
    <div className="relative w-full h-full">
      <div className="absolute top-2 right-3 flex gap-3 text-[9px] text-slate-500 z-10">
        {Object.entries(SEV_COLOR).map(([sev, c]) => (
          <span key={sev} className="flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: c }} />
            {sev}
          </span>
        ))}
      </div>
      <svg ref={svgRef} className="w-full h-full" />
    </div>
  )
}
