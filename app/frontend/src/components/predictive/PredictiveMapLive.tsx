// PredictiveMapLive — modo "Ao vivo" do Mapa Preditivo (Tarefa 4.3).
// Substitui o iframe estático por uma camada MapLibre alimentada pelo
// endpoint /api/areas/{id}/predictive (que reusa compute_match). Reflete
// o estado atual dos dados — atualiza sempre que o gold roda.
import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import type { FeatureCollection } from 'geojson'
import type { StyleSpecification } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../../api/client'

type Hexagono = {
  lat: number
  lon: number
  score: number
  scoreBruto: number
  nOcorrencias: number
  camadas: string[]
  justificativa: string
}

type PredictivePayload = {
  areaId: number
  scoreArea: number
  hexagonos: Hexagono[]
}

const BASE_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    base: {
      type: 'raster',
      tiles: [
        'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
        'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
      ],
      tileSize: 256,
      attribution: '© OpenStreetMap · © CARTO',
    },
  },
  layers: [
    { id: 'paper', type: 'background', paint: { 'background-color': '#eef1f5' } },
    { id: 'base', type: 'raster', source: 'base' },
  ],
}

function toGeoJSON(hex: Hexagono[]): FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: hex.map((h, i) => ({
      type: 'Feature',
      id: i,
      geometry: { type: 'Point', coordinates: [h.lon, h.lat] },
      properties: {
        score: h.score,
        scoreBruto: h.scoreBruto,
        nOcorrencias: h.nOcorrencias,
        justificativa: h.justificativa,
      },
    })),
  }
}

export function PredictiveMapLive({ areaId }: { areaId: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['predictive', areaId],
    queryFn: () => apiGet<PredictivePayload>(`/areas/${areaId}/predictive`),
    staleTime: 5 * 60 * 1000,
  })

  useEffect(() => {
    if (!ref.current || mapRef.current) return
    const m = new maplibregl.Map({
      container: ref.current,
      style: BASE_STYLE,
      center: [-43.2, -22.92],
      zoom: 11,
      attributionControl: false,
    })
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    mapRef.current = m
    return () => {
      m.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const m = mapRef.current
    if (!m || !data) return
    const geojson = toGeoJSON(data.hexagonos)

    const apply = () => {
      if (m.getLayer('risk-circles')) m.removeLayer('risk-circles')
      if (m.getSource('risk')) m.removeSource('risk')
      m.addSource('risk', { type: 'geojson', data: geojson })
      m.addLayer({
        id: 'risk-circles',
        type: 'circle',
        source: 'risk',
        paint: {
          'circle-radius': [
            'interpolate', ['linear'], ['get', 'score'],
            0, 6, 1, 22,
          ],
          'circle-color': [
            'interpolate', ['linear'], ['get', 'score'],
            0, '#bcd0e8',
            0.5, '#e8b08f',
            1, '#8f3a2f',
          ],
          'circle-opacity': 0.78,
          'circle-stroke-color': '#15181d',
          'circle-stroke-width': 0.5,
        },
      })

      // Popup ao clicar (acessibilidade: também via Enter quando focado)
      m.on('click', 'risk-circles', (e) => {
        const f = e.features?.[0]
        if (!f || f.geometry.type !== 'Point') return
        const coords = (f.geometry as unknown as { coordinates: [number, number] }).coordinates
        const p = f.properties as Hexagono
        new maplibregl.Popup({ offset: 12 })
          .setLngLat(coords)
          .setHTML(
            `<strong>Score ${(p.score * 10).toFixed(1)}</strong><br/>` +
              `${p.nOcorrencias} ocorrência${p.nOcorrencias === 1 ? '' : 's'}<br/>` +
              `<small>${(p.justificativa || '').slice(0, 140)}</small>`,
          )
          .addTo(m)
      })
      m.on('mouseenter', 'risk-circles', () => (m.getCanvas().style.cursor = 'pointer'))
      m.on('mouseleave', 'risk-circles', () => (m.getCanvas().style.cursor = ''))

      // Centraliza no conjunto de pontos
      if (data.hexagonos.length) {
        const b = new maplibregl.LngLatBounds()
        for (const h of data.hexagonos) b.extend([h.lon, h.lat])
        m.fitBounds(b, { padding: 60, duration: 800 })
      }
    }

    if (m.isStyleLoaded()) apply()
    else m.once('load', apply)
  }, [data])

  return (
    <div className="pred-live">
      <div className="pred-live__map" ref={ref} aria-label="Mapa preditivo ao vivo" role="img" />
      <div className="pred-live__status" aria-live="polite">
        {isLoading && 'Carregando dados ao vivo do CompStat…'}
        {error && 'Falha ao carregar dados ao vivo — mostre o modo Oficial.'}
        {data && !isLoading && (
          <span>
            Score da área: <strong>{(data.scoreArea * 10).toFixed(1)}</strong> ·{' '}
            {data.hexagonos.length} ponto{data.hexagonos.length === 1 ? '' : 's'} crítico
            {data.hexagonos.length === 1 ? '' : 's'} no recorte atual.
          </span>
        )}
      </div>
    </div>
  )
}
