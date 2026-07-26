"""Chinese coordinate system conversions (GCJ-02 / BD-09 -> WGS-84).

Derived from googollee/eviltransform
(https://github.com/googollee/eviltransform), BSD-2-Clause license.
Copyright (c) 2015 googollee. Redistribution and use in source and binary
forms, with or without modification, are permitted provided that the
conditions of the BSD-2-Clause license are met. Provided "AS IS" without
warranty of any kind.

Only the standard forward transform and its simple inverse are embedded
here (accuracy a few meters, plenty for arcade map pins).
"""

import math

_A = 6378245.0
_EE = 0.00669342162296594323
_X_PI = math.pi * 3000.0 / 180.0


def out_of_china(lat, lng):
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(x, y):
    ret = (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y
           + 0.2 * math.sqrt(abs(x)))
    ret += (20.0 * math.sin(6.0 * x * math.pi)
            + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi)
            + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi)
            + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x, y):
    ret = (300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y
           + 0.1 * math.sqrt(abs(x)))
    ret += (20.0 * math.sin(6.0 * x * math.pi)
            + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi)
            + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi)
            + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def _delta(lat, lng):
    d_lat = _transform_lat(lng - 105.0, lat - 35.0)
    d_lng = _transform_lng(lng - 105.0, lat - 35.0)
    rad_lat = lat / 180.0 * math.pi
    magic = math.sin(rad_lat)
    magic = 1 - _EE * magic * magic
    sqrt_magic = math.sqrt(magic)
    d_lat = (d_lat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrt_magic) * math.pi)
    d_lng = (d_lng * 180.0) / (_A / sqrt_magic * math.cos(rad_lat) * math.pi)
    return d_lat, d_lng


def wgs2gcj(wgs_lat, wgs_lng):
    if out_of_china(wgs_lat, wgs_lng):
        return wgs_lat, wgs_lng
    d_lat, d_lng = _delta(wgs_lat, wgs_lng)
    return wgs_lat + d_lat, wgs_lng + d_lng


def gcj2wgs(gcj_lat, gcj_lng):
    """Simple inverse: subtract the forward delta computed at the GCJ point."""
    if out_of_china(gcj_lat, gcj_lng):
        return gcj_lat, gcj_lng
    d_lat, d_lng = _delta(gcj_lat, gcj_lng)
    return gcj_lat - d_lat, gcj_lng - d_lng


def bd2gcj(bd_lat, bd_lng):
    x = bd_lng - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * _X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * _X_PI)
    return z * math.sin(theta), z * math.cos(theta)


def bd2wgs(bd_lat, bd_lng):
    return gcj2wgs(*bd2gcj(bd_lat, bd_lng))
