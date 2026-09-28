/* CMMS offline UI helpers: tabs + responsive dependency-free charts. */
(function () {
  'use strict';

  function activateTab(button) {
    const selector = button.getAttribute('data-bs-target') || button.getAttribute('href');
    if (!selector || selector.charAt(0) !== '#') return;
    const container = button.closest('[role="tablist"], .nav');
    if (container) {
      container.querySelectorAll('[data-bs-toggle="tab"], [role="tab"]').forEach((node) => {
        node.classList.remove('active');
        node.setAttribute('aria-selected', 'false');
      });
    }
    button.classList.add('active');
    button.setAttribute('aria-selected', 'true');
    const pane = document.querySelector(selector);
    if (!pane) return;
    const parent = pane.parentElement;
    if (parent) parent.querySelectorAll('.tab-pane').forEach((node) => node.classList.remove('show', 'active'));
    pane.classList.add('show', 'active');
  }

  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-bs-toggle="tab"]');
    if (!button) return;
    event.preventDefault();
    activateTab(button);
  });

  window.bootstrap = window.bootstrap || {};
  window.bootstrap.Tab = window.bootstrap.Tab || class Tab {
    constructor(element) { this.element = element; }
    show() { activateTab(this.element); }
    static getOrCreateInstance(element) { return new window.bootstrap.Tab(element); }
  };

  function cssVar(styles, name, fallback) {
    return (styles.getPropertyValue(name) || '').trim() || fallback;
  }

  function compactNumber(value) {
    const n = Number(value) || 0;
    if (Math.abs(n) >= 1000000) return `${(n / 1000000).toFixed(n % 1000000 ? 1 : 0)}M`;
    if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(n % 1000 ? 1 : 0)}k`;
    return Number.isInteger(n) ? String(n) : n.toFixed(1);
  }

  function truncate(ctx, text, maxWidth) {
    const raw = String(text == null ? '' : text);
    if (ctx.measureText(raw).width <= maxWidth) return raw;
    let out = raw;
    while (out.length > 3 && ctx.measureText(`${out}…`).width > maxWidth) out = out.slice(0, -1);
    return `${out}…`;
  }

  function niceMax(value) {
    const max = Math.max(1, Number(value) || 1);
    const magnitude = Math.pow(10, Math.floor(Math.log10(max)));
    const normalized = max / magnitude;
    const step = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
    return step * magnitude;
  }

  if (!window.Chart) {
    window.Chart = class SimpleChart {
      constructor(canvas, config) {
        this.canvas = canvas && canvas.canvas ? canvas.canvas : canvas;
        this.config = config || {};
        this.hitRegions = [];
        this._frame = null;
        this._onClick = (event) => this.handleClick(event);
        this.canvas?.addEventListener('click', this._onClick);
        if ('ResizeObserver' in window && this.canvas) {
          this.resizeObserver = new ResizeObserver(() => this.queueDraw());
          this.resizeObserver.observe(this.canvas.parentElement || this.canvas);
        } else {
          this._onResize = () => this.queueDraw();
          window.addEventListener('resize', this._onResize);
        }
        this.queueDraw();
      }

      destroy() {
        if (this._frame) cancelAnimationFrame(this._frame);
        this.resizeObserver?.disconnect();
        if (this._onResize) window.removeEventListener('resize', this._onResize);
        this.canvas?.removeEventListener('click', this._onClick);
        if (!this.canvas) return;
        const ctx = this.canvas.getContext && this.canvas.getContext('2d');
        if (ctx) ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
      }

      queueDraw() {
        if (this._frame) cancelAnimationFrame(this._frame);
        this._frame = requestAnimationFrame(() => { this._frame = null; this.draw(); });
      }

      handleClick(event) {
        const callback = this.config?.options?.onClick;
        if (typeof callback !== 'function' || !this.canvas) return;
        const rect = this.canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const y = event.clientY - rect.top;
        const hit = this.hitRegions.find((region) => {
          if (region.kind === 'arc') {
            const dx = x - region.cx, dy = y - region.cy;
            const distance = Math.sqrt(dx * dx + dy * dy);
            if (distance < region.inner || distance > region.outer) return false;
            let angle = Math.atan2(dy, dx);
            if (angle < -Math.PI / 2) angle += Math.PI * 2;
            let start = region.start, end = region.end;
            if (start < -Math.PI / 2) start += Math.PI * 2;
            if (end < -Math.PI / 2) end += Math.PI * 2;
            return angle >= start && angle <= end;
          }
          return x >= region.x && x <= region.x + region.w && y >= region.y && y <= region.y + region.h;
        });
        callback(event, hit ? [{ index: hit.index, datasetIndex: hit.datasetIndex || 0 }] : []);
      }

      drawEmpty(ctx, width, height, textColor) {
        ctx.fillStyle = textColor;
        ctx.globalAlpha = 0.6;
        ctx.font = '600 13px system-ui, -apple-system, sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('No data available for this scope', width / 2, height / 2);
        ctx.globalAlpha = 1;
      }

      draw() {
        const canvas = this.canvas;
        if (!canvas || !canvas.getContext) return;
        const rect = canvas.getBoundingClientRect();
        const cssWidth = Math.max(220, rect.width || canvas.clientWidth || 640);
        const cssHeight = Math.max(220, rect.height || canvas.clientHeight || 280);
        const ratio = Math.min(window.devicePixelRatio || 1, 2);
        const pixelWidth = Math.round(cssWidth * ratio), pixelHeight = Math.round(cssHeight * ratio);
        if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
        if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
        const ctx = canvas.getContext('2d');
        ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
        ctx.clearRect(0, 0, cssWidth, cssHeight);
        this.hitRegions = [];

        const data = this.config.data || {};
        const labels = Array.isArray(data.labels) ? data.labels : [];
        const datasets = Array.isArray(data.datasets) ? data.datasets : [];
        const values = datasets.flatMap((dataset) => (dataset.data || []).map((value) => Number(value) || 0));
        const hasData = labels.length && values.some((value) => value !== 0);
        const styles = getComputedStyle(document.documentElement);
        const text = cssVar(styles, '--ink', '#0f172a');
        const muted = cssVar(styles, '--muted', '#64748b');
        const grid = cssVar(styles, '--line', '#e2e8f0');
        const panel = cssVar(styles, '--panel', '#ffffff');
        const colors = [
          cssVar(styles, '--primary', '#315ee8'),
          cssVar(styles, '--success', '#0f9f6e'),
          cssVar(styles, '--warning', '#e08a13'),
          '#7c3aed', '#0891b2', cssVar(styles, '--danger', '#e23b48'), '#475569', '#14b8a6', '#a855f7', '#f59e0b'
        ];

        if (!hasData) { this.drawEmpty(ctx, cssWidth, cssHeight, muted); return; }
        const type = String(this.config.type || 'bar').toLowerCase();
        if (type === 'pie' || type === 'doughnut') {
          this.drawRadial(ctx, cssWidth, cssHeight, labels, datasets, colors, text, muted, panel, type);
        } else {
          this.drawBars(ctx, cssWidth, cssHeight, labels, datasets, colors, text, muted, grid);
        }
      }

      drawRadial(ctx, width, height, labels, datasets, colors, text, muted, panel, type) {
        const values = (datasets[0] && datasets[0].data || []).map((v) => Number(v) || 0);
        const total = values.reduce((sum, value) => sum + value, 0);
        const showLegend = this.config?.options?.plugins?.legend?.display !== false;
        const legendSpace = showLegend ? Math.min(height * 0.45, Math.max(62, Math.ceil(labels.length / 3) * 19 + 18)) : 12;
        const plotHeight = height - legendSpace;
        const cx = width / 2;
        const cy = plotHeight / 2 + 4;
        const outer = Math.max(38, Math.min(width * 0.27, plotHeight * 0.39));
        const inner = type === 'doughnut' ? outer * 0.62 : 0;
        let start = -Math.PI / 2;
        values.forEach((value, index) => {
          if (value <= 0) return;
          const end = start + (value / total) * Math.PI * 2;
          ctx.beginPath();
          ctx.arc(cx, cy, outer, start, end);
          ctx.arc(cx, cy, inner, end, start, true);
          ctx.closePath();
          ctx.fillStyle = colors[index % colors.length];
          ctx.fill();
          ctx.strokeStyle = panel;
          ctx.lineWidth = 2;
          ctx.stroke();
          this.hitRegions.push({ kind: 'arc', cx, cy, inner, outer, start, end, index, datasetIndex: 0 });
          start = end;
        });
        if (type === 'doughnut') {
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillStyle = text;
          ctx.font = '800 24px system-ui, -apple-system, sans-serif';
          ctx.fillText(compactNumber(total), cx, cy - 4);
          ctx.fillStyle = muted;
          ctx.font = '600 10px system-ui, -apple-system, sans-serif';
          ctx.fillText('TOTAL', cx, cy + 17);
        }
        if (!showLegend) return;
        const itemGap = 14;
        const rowHeight = 18;
        ctx.font = '600 11px system-ui, -apple-system, sans-serif';
        let x = 8, y = plotHeight + 20;
        labels.forEach((label, index) => {
          const labelText = `${label} · ${compactNumber(values[index] || 0)}`;
          const itemWidth = Math.min(width - 16, ctx.measureText(labelText).width + 26);
          if (x + itemWidth > width - 8 && x > 8) { x = 8; y += rowHeight; }
          ctx.fillStyle = colors[index % colors.length];
          ctx.beginPath(); ctx.arc(x + 5, y - 3, 4, 0, Math.PI * 2); ctx.fill();
          ctx.fillStyle = muted;
          ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
          ctx.fillText(truncate(ctx, labelText, itemWidth - 20), x + 14, y);
          x += itemWidth + itemGap;
        });
      }

      drawBars(ctx, width, height, labels, datasets, colors, text, muted, grid) {
        const horizontal = this.config?.options?.indexAxis === 'y';
        const allValues = datasets.flatMap((dataset) => (dataset.data || []).map((value) => Number(value) || 0));
        const configuredMax = horizontal ? this.config?.options?.scales?.x?.max : this.config?.options?.scales?.y?.max;
        const maxValue = Number(configuredMax) || niceMax(Math.max(...allValues, 1));
        if (horizontal) this.drawHorizontalBars(ctx, width, height, labels, datasets, colors, text, muted, grid, maxValue);
        else this.drawVerticalBars(ctx, width, height, labels, datasets, colors, text, muted, grid, maxValue);
      }

      drawVerticalBars(ctx, width, height, labels, datasets, colors, text, muted, grid, maxValue) {
        const left = 45, right = 16, top = 18, bottom = labels.length > 7 ? 68 : 52;
        const plotW = Math.max(30, width - left - right), plotH = Math.max(40, height - top - bottom);
        ctx.font = '500 10px system-ui, -apple-system, sans-serif';
        ctx.textBaseline = 'middle';
        for (let step = 0; step <= 4; step++) {
          const value = maxValue * step / 4;
          const y = top + plotH - plotH * step / 4;
          ctx.strokeStyle = grid; ctx.lineWidth = 1;
          ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(left + plotW, y); ctx.stroke();
          ctx.fillStyle = muted; ctx.textAlign = 'right'; ctx.fillText(compactNumber(value), left - 8, y);
        }
        const groupW = plotW / Math.max(1, labels.length);
        const seriesCount = Math.max(1, datasets.length);
        labels.forEach((label, i) => {
          datasets.forEach((dataset, j) => {
            const value = Number((dataset.data || [])[i]) || 0;
            const slot = Math.min(groupW * .72, 54);
            const barW = Math.max(3, slot / seriesCount);
            const x = left + i * groupW + (groupW - slot) / 2 + j * barW;
            const h = Math.max(value > 0 ? 2 : 0, (value / maxValue) * plotH);
            const y = top + plotH - h;
            ctx.fillStyle = colors[j % colors.length];
            ctx.beginPath();
            if (ctx.roundRect) ctx.roundRect(x, y, Math.max(2, barW - 2), h, Math.min(5, barW / 3));
            else ctx.rect(x, y, Math.max(2, barW - 2), h);
            ctx.fill();
            this.hitRegions.push({ kind: 'rect', x, y, w: Math.max(2, barW - 2), h, index: i, datasetIndex: j });
            if (value > 0 && barW > 18) {
              ctx.fillStyle = text; ctx.textAlign = 'center'; ctx.font = '700 10px system-ui, sans-serif';
              ctx.fillText(compactNumber(value), x + (barW - 2) / 2, Math.max(9, y - 8));
            }
          });
          ctx.save();
          ctx.translate(left + i * groupW + groupW / 2, top + plotH + 13);
          if (labels.length > 5) ctx.rotate(-0.42);
          ctx.fillStyle = muted; ctx.font = '600 10px system-ui, -apple-system, sans-serif';
          ctx.textAlign = labels.length > 5 ? 'right' : 'center';
          ctx.fillText(truncate(ctx, label, Math.max(54, groupW * 1.35)), 0, 0);
          ctx.restore();
        });
      }

      drawHorizontalBars(ctx, width, height, labels, datasets, colors, text, muted, grid, maxValue) {
        const maxLabelWidth = Math.min(150, Math.max(78, width * .28));
        const left = maxLabelWidth + 16, right = 38, top = 12, bottom = 30;
        const plotW = Math.max(50, width - left - right), plotH = Math.max(50, height - top - bottom);
        const rowH = plotH / Math.max(1, labels.length);
        ctx.font = '600 10px system-ui, -apple-system, sans-serif';
        ctx.textBaseline = 'middle';
        for (let step = 0; step <= 4; step++) {
          const x = left + plotW * step / 4;
          ctx.strokeStyle = grid; ctx.beginPath(); ctx.moveTo(x, top); ctx.lineTo(x, top + plotH); ctx.stroke();
          ctx.fillStyle = muted; ctx.textAlign = 'center'; ctx.fillText(compactNumber(maxValue * step / 4), x, top + plotH + 17);
        }
        labels.forEach((label, i) => {
          const yCenter = top + i * rowH + rowH / 2;
          ctx.fillStyle = muted; ctx.textAlign = 'right'; ctx.font = '600 10px system-ui, -apple-system, sans-serif';
          ctx.fillText(truncate(ctx, label, maxLabelWidth), left - 9, yCenter);
          const seriesCount = Math.max(1, datasets.length);
          datasets.forEach((dataset, j) => {
            const value = Number((dataset.data || [])[i]) || 0;
            const barH = Math.max(5, Math.min(20, rowH * .55 / seriesCount));
            const y = yCenter - (seriesCount * barH) / 2 + j * barH;
            const w = Math.max(value > 0 ? 2 : 0, (value / maxValue) * plotW);
            ctx.fillStyle = colors[j % colors.length];
            ctx.beginPath();
            if (ctx.roundRect) ctx.roundRect(left, y, w, Math.max(3, barH - 2), 4); else ctx.rect(left, y, w, Math.max(3, barH - 2));
            ctx.fill();
            this.hitRegions.push({ kind: 'rect', x: left, y, w, h: Math.max(3, barH - 2), index: i, datasetIndex: j });
            if (value > 0) {
              ctx.fillStyle = text; ctx.textAlign = 'left'; ctx.font = '700 10px system-ui, sans-serif';
              ctx.fillText(compactNumber(value), Math.min(width - 28, left + w + 6), y + (barH - 2) / 2);
            }
          });
        });
      }
    };
  }
})();
