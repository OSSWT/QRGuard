/// Circular risk-score indicator, 0-100.
///
/// The number is drawn in the centre alongside the verdict word, so the score is never
/// communicated by colour alone.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

class RiskDial extends StatelessWidget {
  const RiskDial({
    super.key,
    required this.score,
    required this.color,
    required this.label,
    this.size = 168,
  });

  final int score;
  final Color color;
  final String label;
  final double size;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: TweenAnimationBuilder<double>(
        tween: Tween(begin: 0, end: score / 100),
        duration: const Duration(milliseconds: 700),
        curve: Curves.easeOutCubic,
        builder: (context, value, _) => CustomPaint(
          painter: _DialPainter(progress: value, color: color),
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '${(value * 100).round()}',
                  style: TextStyle(
                    fontSize: size * 0.28,
                    fontWeight: FontWeight.bold,
                    color: color,
                    height: 1.1,
                  ),
                ),
                Text(
                  '/ 100',
                  style: TextStyle(
                    fontSize: size * 0.09,
                    color: Colors.black54,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  label,
                  style: TextStyle(
                    fontSize: size * 0.10,
                    fontWeight: FontWeight.w700,
                    color: color,
                    letterSpacing: 1.1,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _DialPainter extends CustomPainter {
  _DialPainter({required this.progress, required this.color});

  final double progress;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final stroke = size.width * 0.075;
    final rect =
        Offset(stroke / 2, stroke / 2) &
        Size(size.width - stroke, size.height - stroke);

    final track = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..color = color.withValues(alpha: 0.15);

    final arc = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..color = color;

    // Leave a gap at the bottom so the arc reads as a gauge, not a pie chart.
    const startAngle = math.pi * 0.75;
    const sweepAngle = math.pi * 1.5;
    canvas.drawArc(rect, startAngle, sweepAngle, false, track);
    canvas.drawArc(rect, startAngle, sweepAngle * progress, false, arc);
  }

  @override
  bool shouldRepaint(_DialPainter old) =>
      old.progress != progress || old.color != color;
}
