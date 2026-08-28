/// QRGuard brand artwork plus unobtrusive camera and analysis frames.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme.dart';

/// The same user-approved artwork used by the Android launcher icon.
class PulseLensMark extends StatelessWidget {
  const PulseLensMark({super.key, this.size = 42});

  final double size;

  @override
  Widget build(BuildContext context) => ClipRRect(
    borderRadius: BorderRadius.circular(size * 0.12),
    child: Image.asset(
      'assets/icon/qrguard_icon_source.png',
      width: size,
      height: size,
      fit: BoxFit.cover,
      filterQuality: FilterQuality.high,
      semanticLabel: 'QRGuard',
    ),
  );
}

/// Four clean scan corners over the live camera feed.
///
/// The previous decorative rings and signal pulses were removed so the centre
/// remains an unobstructed real-world camera preview, similar to wallet-app QR
/// scanners. This painter never supplies or simulates camera content.
class LiveCameraFrame extends StatelessWidget {
  const LiveCameraFrame({super.key, this.detected = false});

  final bool detected;

  @override
  Widget build(BuildContext context) => IgnorePointer(
    child: CustomPaint(
      painter: _LiveCameraFramePainter(
        brand: context.qrColors.brand,
        light: context.qrColors.signalLight,
        detected: detected,
      ),
      child: const SizedBox.expand(),
    ),
  );
}

class AnalysisLens extends StatelessWidget {
  const AnalysisLens({super.key, required this.child, this.size = 224});

  final Widget child;
  final double size;

  @override
  Widget build(BuildContext context) => SizedBox.square(
    dimension: size,
    child: Stack(
      alignment: Alignment.center,
      children: [
        CustomPaint(
          size: Size.square(size),
          painter: _AnalysisLensPainter(
            brand: context.qrColors.brand,
            muted: context.qrColors.mutedStructure,
          ),
        ),
        ClipRRect(
          borderRadius: BorderRadius.circular(12),
          child: SizedBox.square(dimension: size * 0.56, child: child),
        ),
      ],
    ),
  );
}

List<Path> _cornerPaths(Size size, double arm, double inset) {
  final right = size.width - inset;
  final bottom = size.height - inset;
  return [
    Path()
      ..moveTo(inset + arm, inset)
      ..lineTo(inset, inset)
      ..lineTo(inset, inset + arm),
    Path()
      ..moveTo(right - arm, inset)
      ..lineTo(right, inset)
      ..lineTo(right, inset + arm),
    Path()
      ..moveTo(inset, bottom - arm)
      ..lineTo(inset, bottom)
      ..lineTo(inset + arm, bottom),
    Path()
      ..moveTo(right, bottom - arm)
      ..lineTo(right, bottom)
      ..lineTo(right - arm, bottom),
  ];
}

class _LiveCameraFramePainter extends CustomPainter {
  const _LiveCameraFramePainter({
    required this.brand,
    required this.light,
    required this.detected,
  });

  final Color brand;
  final Color light;
  final bool detected;

  @override
  void paint(Canvas canvas, Size size) {
    final side = size.shortestSide;
    final paint = Paint()
      ..color = detected ? light : brand
      ..style = PaintingStyle.stroke
      ..strokeWidth = math.max(3, side * 0.018)
      ..strokeCap = StrokeCap.round;
    for (final path in _cornerPaths(size, side * 0.18, side * 0.08)) {
      canvas.drawPath(path, paint);
    }
  }

  @override
  bool shouldRepaint(covariant _LiveCameraFramePainter oldDelegate) =>
      oldDelegate.brand != brand ||
      oldDelegate.light != light ||
      oldDelegate.detected != detected;
}

class _AnalysisLensPainter extends CustomPainter {
  const _AnalysisLensPainter({required this.brand, required this.muted});

  final Color brand;
  final Color muted;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    for (var index = 0; index < 3; index++) {
      canvas.drawCircle(
        center,
        size.shortestSide * (0.34 + index * 0.07),
        Paint()
          ..color = (index == 0 ? brand : muted).withValues(
            alpha: 0.72 - index * 0.16,
          )
          ..style = PaintingStyle.stroke
          ..strokeWidth = index == 0 ? 2.5 : 1.4,
      );
    }
    final bracketPaint = Paint()
      ..color = brand
      ..style = PaintingStyle.stroke
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round;
    for (final path in _cornerPaths(
      size,
      size.shortestSide * 0.10,
      size.shortestSide * 0.16,
    )) {
      canvas.drawPath(path, bracketPaint);
    }
  }

  @override
  bool shouldRepaint(covariant _AnalysisLensPainter oldDelegate) =>
      oldDelegate.brand != brand || oldDelegate.muted != muted;
}
