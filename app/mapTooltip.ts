import L from 'leaflet';

const MARGIN = 8;

// Leaflet sizes a tooltip to its longest line (white-space: nowrap) and always
// opens it on the side it was bound to, so a long institution note runs off
// the map and a pie near the top edge opens above the frame. Here the text
// wraps at a fixed width, and on every opening the tooltip is placed above or
// below the marker, whichever has room, and slid sideways to stay inside.
export function bindFittedTooltip(marker: L.Marker, html: string, gap: number) {
  marker.bindTooltip(html, { direction: 'top', offset: [0, -gap], className: 'map-tip' });
  marker.on('tooltipopen', (e: L.TooltipEvent) => {
    const map = (marker as any)._map as L.Map | undefined;
    const el = e.tooltip.getElement();
    if (!map || !el) return;
    const size = map.getSize();
    const at = map.latLngToContainerPoint(marker.getLatLng());
    const w = el.offsetWidth, h = el.offsetHeight;
    const above = at.y - gap - h >= MARGIN || at.y + gap + h > size.y - MARGIN;
    const left = at.x - w / 2;
    const dx = Math.max(MARGIN - left, Math.min(0, size.x - MARGIN - (left + w)));
    e.tooltip.options.direction = above ? 'top' : 'bottom';
    e.tooltip.options.offset = L.point(dx, above ? -gap : gap);
    el.classList.toggle('map-tip-shifted', Math.abs(dx) > 1);
    e.tooltip.update();
  });
}
