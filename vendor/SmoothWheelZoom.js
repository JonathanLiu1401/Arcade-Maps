/*!
 * Leaflet.SmoothWheelZoom - continuous, fractional mouse-wheel zoom for Leaflet.
 *
 * Copyright (c) 2019 mutsuyuki
 * https://github.com/mutsuyuki/Leaflet.SmoothWheelZoom
 * Licensed under the MIT License (see vendor/LICENSES.txt).
 *
 * Local adaptation for Arcade Maps (Leaflet 1.9.4). Upstream logic is kept;
 * three robustness fixes were applied, each marked "AM fix" below:
 *   1. _updateWheelZoom returned without re-arming requestAnimationFrame when
 *      the pointer sat exactly on the map centre, silently killing the gesture.
 *   2. The "map moved underneath us" guard returned while _isWheeling stayed
 *      true, so the handler deadlocked and no later wheel event restarted the
 *      animation loop. It now ends the gesture cleanly.
 *   3. _onWheelEnd did not clear the pending idle timer, so the timer could
 *      fire a second _moveEnd(true) - a duplicate zoomend, which costs an
 *      extra marker re-cluster and an extra hash write.
 * Also added: removeHooks now cancels any in-flight frame and timer.
 */
(function () {
  "use strict";

  L.Map.mergeOptions({
    /* Whether the wheel zooms smoothly. Pass 'center' to always zoom to the
       centre of the view rather than the pointer. */
    smoothWheelZoom: true,
    /* Zoom levels applied per unit of L.DomEvent.getWheelDelta. */
    smoothSensitivity: 1
  });

  L.Map.SmoothWheelZoom = L.Handler.extend({

    addHooks: function () {
      L.DomEvent.on(this._map._container, "wheel", this._onWheelScroll, this);
    },

    removeHooks: function () {
      L.DomEvent.off(this._map._container, "wheel", this._onWheelScroll, this);
      /* AM fix 3 (cleanup): never leave a frame or timer armed. */
      if (this._zoomAnimationId) cancelAnimationFrame(this._zoomAnimationId);
      clearTimeout(this._timeoutId);
      this._zoomAnimationId = null;
      this._isWheeling = false;
    },

    _onWheelScroll: function (e) {
      if (!this._isWheeling) this._onWheelStart(e);
      this._onWheeling(e);
    },

    _onWheelStart: function (e) {
      var map = this._map;
      this._isWheeling = true;
      this._wheelMousePosition = map.mouseEventToContainerPoint(e);
      this._centerPoint = map.getSize()._divideBy(2);
      this._startLatLng = map.containerPointToLatLng(this._centerPoint);
      this._wheelMouseLatLng = map.containerPointToLatLng(this._wheelMousePosition);
      this._startZoom = map.getZoom();
      this._moved = false;
      this._zooming = true;

      map._stop();
      if (map._panAnim) map._panAnim.stop();

      this._goalZoom = map.getZoom();
      this._prevCenter = map.getCenter();
      this._prevZoom = map.getZoom();

      this._zoomAnimationId = requestAnimationFrame(this._updateWheelZoom.bind(this));
    },

    _onWheeling: function (e) {
      var map = this._map;

      this._goalZoom = this._goalZoom +
        L.DomEvent.getWheelDelta(e) * 0.003 * map.options.smoothSensitivity;
      if (this._goalZoom < map.getMinZoom() || this._goalZoom > map.getMaxZoom()) {
        this._goalZoom = map._limitZoom(this._goalZoom);
      }
      this._wheelMousePosition = map.mouseEventToContainerPoint(e);
      this._wheelMouseLatLng = map.containerPointToLatLng(this._wheelMousePosition);

      clearTimeout(this._timeoutId);
      this._timeoutId = setTimeout(this._onWheelEnd.bind(this), 200);

      L.DomEvent.preventDefault(e);
      L.DomEvent.stopPropagation(e);
    },

    _onWheelEnd: function () {
      if (!this._isWheeling) return;
      this._isWheeling = false;
      this._zooming = false;
      /* AM fix 3: drop the idle timer so it cannot fire a second _moveEnd. */
      clearTimeout(this._timeoutId);
      this._timeoutId = null;
      if (this._zoomAnimationId) cancelAnimationFrame(this._zoomAnimationId);
      this._zoomAnimationId = null;
      /* Fires zoomend + moveend once: markercluster re-clusters here. */
      this._map._moveEnd(true);
    },

    _updateWheelZoom: function () {
      var map = this._map;

      /* AM fix 2: something else moved the map (flyTo, setView, resize).
         End the gesture instead of returning with _isWheeling still true. */
      if (!map.getCenter().equals(this._prevCenter) || map.getZoom() !== this._prevZoom) {
        this._onWheelEnd();
        return;
      }

      this._zoom = map.getZoom() + (this._goalZoom - map.getZoom()) * 0.3;
      this._zoom = Math.floor(this._zoom * 100) / 100;

      var delta = this._wheelMousePosition.subtract(this._centerPoint);

      if (map.options.smoothWheelZoom === "center" || (delta.x === 0 && delta.y === 0)) {
        /* AM fix 1: pointer exactly on centre is a valid state - zoom about
           the centre and keep the animation loop alive. */
        this._center = this._startLatLng;
      } else {
        this._center = map.unproject(
          map.project(this._wheelMouseLatLng, this._zoom).subtract(delta), this._zoom);
      }

      if (!this._moved) {
        map._moveStart(true, false);
        this._moved = true;
      }

      map._move(this._center, this._zoom);
      this._prevCenter = map.getCenter();
      this._prevZoom = map.getZoom();

      this._zoomAnimationId = requestAnimationFrame(this._updateWheelZoom.bind(this));
    }

  });

  L.Map.addInitHook("addHandler", "smoothWheelZoom", L.Map.SmoothWheelZoom);
})();
