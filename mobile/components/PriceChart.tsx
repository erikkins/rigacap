/**
 * Interactive price chart with DWAP overlay, breakout trigger line,
 * entry date marker, and touch crosshair.
 *
 * Portrait: compact chart. Landscape: full-screen immersive.
 */

import React, { useMemo, useState } from 'react';
import { Dimensions, StyleSheet, Text, View } from 'react-native';
import Svg, {
  Circle,
  Defs,
  Line,
  LinearGradient,
  Path,
  Rect,
  Stop,
  Text as SvgText,
} from 'react-native-svg';
import {
  Gesture,
  GestureDetector,
  GestureHandlerRootView,
} from 'react-native-gesture-handler';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  runOnJS,
} from 'react-native-reanimated';
import { Colors, FontSize, Spacing } from '@/constants/theme';
import { ChartPoint } from '@/hooks/useChartData';

interface PriceChartProps {
  data: ChartPoint[];
  entryDate?: string | null;
  breakoutDate?: string | null;
  isLandscape?: boolean;
}

const PADDING = { top: 20, right: 12, bottom: 28, left: 56 };

export default function PriceChart({
  data,
  entryDate,
  breakoutDate,
  isLandscape,
}: PriceChartProps) {
  const [crosshair, setCrosshair] = useState<{
    x: number;
    y: number;
    idx: number;
  } | null>(null);

  const [viewRange, setViewRange] = useState<{ start: number; end: number }>({
    start: 0,
    end: data.length - 1,
  });

  // Reset view range when data changes
  React.useEffect(() => {
    setViewRange({ start: 0, end: data.length - 1 });
  }, [data.length]);

  const window = Dimensions.get('window');
  const chartWidth = isLandscape ? window.width : window.width - Spacing.md * 2;
  const chartHeight = isLandscape ? window.height - 60 : 220;

  const plotW = chartWidth - PADDING.left - PADDING.right;
  const plotH = chartHeight - PADDING.top - PADDING.bottom;

  const visibleData = useMemo(
    () => data.slice(viewRange.start, viewRange.end + 1),
    [data, viewRange]
  );

  // Price range for Y axis
  const { minPrice, maxPrice, minDwap, maxAll } = useMemo(() => {
    if (!visibleData.length) return { minPrice: 0, maxPrice: 100, minDwap: 0, maxAll: 100 };
    let lo = Infinity;
    let hi = -Infinity;
    let dLo = Infinity;
    visibleData.forEach((p) => {
      lo = Math.min(lo, p.low);
      hi = Math.max(hi, p.high);
      if (p.dwap != null) {
        dLo = Math.min(dLo, p.dwap);
        lo = Math.min(lo, p.dwap);
        hi = Math.max(hi, p.dwap * 1.05);
      }
    });
    // 5% padding
    const range = hi - lo || 1;
    return {
      minPrice: lo - range * 0.05,
      maxPrice: hi + range * 0.05,
      minDwap: dLo,
      maxAll: hi + range * 0.05,
    };
  }, [visibleData]);

  // Map data to SVG coords
  const toX = (i: number) => PADDING.left + (i / Math.max(visibleData.length - 1, 1)) * plotW;
  const toY = (price: number) =>
    PADDING.top + (1 - (price - minPrice) / (maxPrice - minPrice || 1)) * plotH;

  // Build SVG paths
  const { pricePath, dwapPath, breakoutPath, areaPath } = useMemo(() => {
    if (!visibleData.length) return { pricePath: '', dwapPath: '', breakoutPath: '', areaPath: '' };

    let price = '';
    let dwap = '';
    let breakout = '';
    let area = '';
    let dwapStarted = false;
    let breakoutStarted = false;

    visibleData.forEach((p, i) => {
      const x = toX(i);
      const yClose = toY(p.close);

      // Price line
      price += i === 0 ? `M${x},${yClose}` : `L${x},${yClose}`;

      // Area under price line
      if (i === 0) {
        area = `M${x},${PADDING.top + plotH}L${x},${yClose}`;
      } else {
        area += `L${x},${yClose}`;
      }
      if (i === visibleData.length - 1) {
        area += `L${x},${PADDING.top + plotH}Z`;
      }

      // DWAP line
      if (p.dwap != null) {
        const yDwap = toY(p.dwap);
        dwap += dwapStarted ? `L${x},${yDwap}` : `M${x},${yDwap}`;
        dwapStarted = true;

        // Breakout trigger (DWAP * 1.05)
        const yBreakout = toY(p.dwap * 1.05);
        breakout += breakoutStarted ? `L${x},${yBreakout}` : `M${x},${yBreakout}`;
        breakoutStarted = true;
      }
    });

    return { pricePath: price, dwapPath: dwap, breakoutPath: breakout, areaPath: area };
  }, [visibleData, minPrice, maxPrice]);

  // Entry date marker
  const entryX = useMemo(() => {
    if (!entryDate || !visibleData.length) return null;
    const idx = visibleData.findIndex((p) => p.date === entryDate);
    if (idx < 0) return null;
    return { x: toX(idx), idx };
  }, [entryDate, visibleData, minPrice, maxPrice]);

  // Breakout date marker
  const breakoutX = useMemo(() => {
    if (!breakoutDate || !visibleData.length) return null;
    const idx = visibleData.findIndex((p) => p.date === breakoutDate);
    if (idx < 0) return null;
    return { x: toX(idx), idx };
  }, [breakoutDate, visibleData, minPrice, maxPrice]);

  // Y-axis labels
  const yLabels = useMemo(() => {
    const count = isLandscape ? 6 : 4;
    const labels: { y: number; label: string }[] = [];
    for (let i = 0; i <= count; i++) {
      const price = minPrice + (i / count) * (maxPrice - minPrice);
      labels.push({ y: toY(price), label: `$${price.toFixed(0)}` });
    }
    return labels;
  }, [minPrice, maxPrice, isLandscape]);

  // X-axis labels
  const xLabels = useMemo(() => {
    if (!visibleData.length) return [];
    const count = isLandscape ? 8 : 4;
    const labels: { x: number; label: string }[] = [];
    for (let i = 0; i <= count; i++) {
      const idx = Math.round((i / count) * (visibleData.length - 1));
      const d = visibleData[idx];
      if (d) {
        const parts = d.date.split('-');
        labels.push({
          x: toX(idx),
          label: `${parseInt(parts[1])}/${parseInt(parts[2])}`,
        });
      }
    }
    return labels;
  }, [visibleData, isLandscape]);

  // Touch / pan gesture for crosshair
  const updateCrosshair = (absX: number) => {
    const relX = absX - PADDING.left;
    if (relX < 0 || relX > plotW || !visibleData.length) {
      setCrosshair(null);
      return;
    }
    const idx = Math.round((relX / plotW) * (visibleData.length - 1));
    const clamped = Math.max(0, Math.min(visibleData.length - 1, idx));
    setCrosshair({ x: toX(clamped), y: toY(visibleData[clamped].close), idx: clamped });
  };

  const clearCrosshair = () => setCrosshair(null);

  const panGesture = Gesture.Pan()
    .onStart((e) => { runOnJS(updateCrosshair)(e.x); })
    .onUpdate((e) => { runOnJS(updateCrosshair)(e.x); })
    .onEnd(() => { runOnJS(clearCrosshair)(); })
    .minDistance(0);

  const longPressGesture = Gesture.LongPress()
    .onStart((e) => { runOnJS(updateCrosshair)(e.x); })
    .minDuration(100);

  const composed = Gesture.Race(panGesture, longPressGesture);

  // Pinch-to-zoom
  const baseStart = useSharedValue(0);
  const baseEnd = useSharedValue(data.length - 1);

  const pinchGesture = Gesture.Pinch()
    .onStart(() => {
      baseStart.value = viewRange.start;
      baseEnd.value = viewRange.end;
    })
    .onUpdate((e) => {
      const currentLen = baseEnd.value - baseStart.value;
      const newLen = Math.max(20, Math.round(currentLen / e.scale));
      const center = Math.round((baseStart.value + baseEnd.value) / 2);
      const newStart = Math.max(0, center - Math.round(newLen / 2));
      const newEnd = Math.min(data.length - 1, newStart + newLen);
      runOnJS(setViewRange)({ start: newStart, end: newEnd });
    });

  const allGestures = Gesture.Simultaneous(composed, pinchGesture);

  const crosshairPoint = crosshair ? visibleData[crosshair.idx] : null;

  if (!data.length) return null;

  return (
    <View style={isLandscape ? styles.landscapeContainer : styles.container}>
      {/* Crosshair tooltip */}
      {crosshairPoint && (
        <View style={[styles.tooltip, isLandscape && styles.tooltipLandscape]}>
          <Text style={styles.tooltipDate}>{crosshairPoint.date}</Text>
          <Text style={styles.tooltipPrice}>${crosshairPoint.close.toFixed(2)}</Text>
          {crosshairPoint.dwap != null && (
            <Text style={styles.tooltipDwap}>
              Wtd Avg: ${crosshairPoint.dwap.toFixed(2)}
            </Text>
          )}
        </View>
      )}

      <GestureHandlerRootView style={{ flex: 1 }}>
        <GestureDetector gesture={allGestures}>
          <Animated.View>
            <Svg width={chartWidth} height={chartHeight}>
              <Defs>
                <LinearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <Stop offset="0" stopColor={Colors.gold} stopOpacity="0.25" />
                  <Stop offset="1" stopColor={Colors.gold} stopOpacity="0.02" />
                </LinearGradient>
              </Defs>

              {/* Y-axis grid lines + labels */}
              {yLabels.map((l, i) => (
                <React.Fragment key={`y${i}`}>
                  <Line
                    x1={PADDING.left}
                    y1={l.y}
                    x2={chartWidth - PADDING.right}
                    y2={l.y}
                    stroke={Colors.cardBorder}
                    strokeWidth={0.5}
                  />
                  <SvgText
                    x={PADDING.left - 6}
                    y={l.y + 4}
                    fontSize={10}
                    fill={Colors.textMuted}
                    textAnchor="end"
                  >
                    {l.label}
                  </SvgText>
                </React.Fragment>
              ))}

              {/* X-axis labels */}
              {xLabels.map((l, i) => (
                <SvgText
                  key={`x${i}`}
                  x={l.x}
                  y={chartHeight - 6}
                  fontSize={10}
                  fill={Colors.textMuted}
                  textAnchor="middle"
                >
                  {l.label}
                </SvgText>
              ))}

              {/* Area fill under price */}
              {areaPath ? (
                <Path d={areaPath} fill="url(#areaGrad)" />
              ) : null}

              {/* DWAP line */}
              {dwapPath ? (
                <Path
                  d={dwapPath}
                  stroke={Colors.blue}
                  strokeWidth={1}
                  fill="none"
                  opacity={0.6}
                />
              ) : null}

              {/* Breakout trigger (DWAP * 1.05) */}
              {breakoutPath ? (
                <Path
                  d={breakoutPath}
                  stroke={Colors.green}
                  strokeWidth={1}
                  strokeDasharray="4,4"
                  fill="none"
                  opacity={0.5}
                />
              ) : null}

              {/* Price line */}
              {pricePath ? (
                <Path
                  d={pricePath}
                  stroke={Colors.gold}
                  strokeWidth={1.5}
                  fill="none"
                />
              ) : null}

              {/* Breakout date marker */}
              {breakoutX && (
                <>
                  <Line
                    x1={breakoutX.x}
                    y1={PADDING.top}
                    x2={breakoutX.x}
                    y2={PADDING.top + plotH}
                    stroke={Colors.gold}
                    strokeWidth={1}
                    strokeDasharray="4,4"
                    opacity={0.7}
                  />
                  <SvgText
                    x={breakoutX.x}
                    y={PADDING.top - 4}
                    fontSize={9}
                    fill={Colors.gold}
                    textAnchor={breakoutX.x > chartWidth - 50 ? 'end' : breakoutX.x < PADDING.left + 50 ? 'start' : 'middle'}
                    fontWeight="600"
                  >
                    BREAKOUT
                  </SvgText>
                </>
              )}

              {/* Entry date marker */}
              {entryX && (
                <>
                  <Line
                    x1={entryX.x}
                    y1={PADDING.top}
                    x2={entryX.x}
                    y2={PADDING.top + plotH}
                    stroke={Colors.green}
                    strokeWidth={1}
                    strokeDasharray="3,3"
                    opacity={0.7}
                  />
                  <SvgText
                    x={entryX.x}
                    y={PADDING.top - 4}
                    fontSize={9}
                    fill={Colors.green}
                    textAnchor={entryX.x > chartWidth - 40 ? 'end' : entryX.x < PADDING.left + 40 ? 'start' : 'middle'}
                    fontWeight="600"
                  >
                    ENTRY
                  </SvgText>
                </>
              )}

              {/* Crosshair */}
              {crosshair && (
                <>
                  <Line
                    x1={crosshair.x}
                    y1={PADDING.top}
                    x2={crosshair.x}
                    y2={PADDING.top + plotH}
                    stroke={Colors.textMuted}
                    strokeWidth={0.5}
                    strokeDasharray="2,2"
                  />
                  <Line
                    x1={PADDING.left}
                    y1={crosshair.y}
                    x2={chartWidth - PADDING.right}
                    y2={crosshair.y}
                    stroke={Colors.textMuted}
                    strokeWidth={0.5}
                    strokeDasharray="2,2"
                  />
                  <Circle
                    cx={crosshair.x}
                    cy={crosshair.y}
                    r={4}
                    fill={Colors.gold}
                    stroke={Colors.background}
                    strokeWidth={2}
                  />
                </>
              )}
            </Svg>
          </Animated.View>
        </GestureDetector>
      </GestureHandlerRootView>

      {/* Legend */}
      <View style={[styles.legend, isLandscape && styles.legendLandscape]}>
        <View style={styles.legendItem}>
          <View style={[styles.legendLine, { backgroundColor: Colors.gold }]} />
          <Text style={styles.legendText}>Price</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.legendLine, { backgroundColor: Colors.blue, opacity: 0.6 }]} />
          <Text style={styles.legendText}>Wtd Avg</Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.legendDashed, { borderColor: Colors.green }]} />
          <Text style={styles.legendText}>Trigger</Text>
        </View>
        {breakoutDate && (
          <View style={styles.legendItem}>
            <View style={[styles.legendDashed, { borderColor: Colors.gold }]} />
            <Text style={styles.legendText}>Breakout</Text>
          </View>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: Colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
    padding: Spacing.xs,
    overflow: 'hidden',
  },
  landscapeContainer: {
    flex: 1,
    backgroundColor: Colors.background,
  },
  tooltip: {
    position: 'absolute',
    top: Spacing.xs,
    right: Spacing.md,
    backgroundColor: Colors.navy + 'EE',
    borderRadius: 8,
    padding: Spacing.sm,
    zIndex: 10,
    borderWidth: 1,
    borderColor: Colors.cardBorder,
  },
  tooltipLandscape: {
    top: Spacing.md,
    right: Spacing.lg,
  },
  tooltipDate: {
    color: Colors.textMuted,
    fontSize: FontSize.xs,
  },
  tooltipPrice: {
    color: Colors.gold,
    fontSize: FontSize.md,
    fontWeight: '700',
  },
  tooltipDwap: {
    color: Colors.blue,
    fontSize: FontSize.xs,
    marginTop: 2,
  },
  legend: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: Spacing.md,
    paddingTop: Spacing.xs,
    paddingBottom: Spacing.xs,
  },
  legendLandscape: {
    position: 'absolute',
    bottom: Spacing.sm,
    left: 0,
    right: 0,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  legendLine: {
    width: 16,
    height: 2,
    borderRadius: 1,
  },
  legendDashed: {
    width: 16,
    height: 0,
    borderTopWidth: 2,
    borderStyle: 'dashed',
  },
  legendText: {
    color: Colors.textMuted,
    fontSize: FontSize.xs,
  },
});
