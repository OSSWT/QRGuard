/// One low-cost painter for the app-wide diagonal "QR CODE" Morse shower.
///
/// Six deliberately separated streams travel from upper-right to lower-left.
/// Each stream has a quiet part in its cycle, and the Morse marks use generous
/// symbol, letter and word gaps, so the field reads as intermittent meteor
/// rain rather than a continuous wall of signals. One painter and one shared
/// controller keep it affordable on the 1 GB target emulator.
library;

import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../theme.dart';

class MorseSignalBackground extends StatefulWidget {
  const MorseSignalBackground({
    super.key,
    required this.child,
    required this.reduceMotion,
  });

  final Widget child;
  final bool reduceMotion;

  @override
  State<MorseSignalBackground> createState() => _MorseSignalBackgroundState();
}

class _MorseSignalBackgroundState extends State<MorseSignalBackground>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 24),
    value: 0.31,
  );
  bool _foreground = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _syncMotion();
  }

  @override
  void didUpdateWidget(covariant MorseSignalBackground oldWidget) {
    super.didUpdateWidget(oldWidget);
    _syncMotion();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    _syncMotion();
  }

  void _syncMotion() {
    final systemDisabled =
        MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final tickerEnabled = TickerMode.valuesOf(context).enabled;
    final shouldMove =
        !widget.reduceMotion && !systemDisabled && tickerEnabled && _foreground;
    if (shouldMove && !_controller.isAnimating) {
      _controller.repeat();
    } else if (!shouldMove && _controller.isAnimating) {
      _controller.stop();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.qrColors;
    return ColoredBox(
      color: colors.background,
      child: CustomPaint(
        painter: _MorseMeteorPainter(
          progress: _controller,
          color: colors.morse,
          opacity: colors.morseOpacity,
        ),
        child: widget.child,
      ),
    );
  }
}

class _MorseMeteorPainter extends CustomPainter {
  _MorseMeteorPainter({
    required this.progress,
    required this.color,
    required this.opacity,
  }) : super(repaint: progress);

  final Animation<double> progress;
  final Color color;
  final double opacity;

  /// Q R (word gap) C O D E. `null` separates the two words.
  static const _letters = <String?>[
    '--.-',
    '.-.',
    null,
    '-.-.',
    '---',
    '-..',
    '.',
  ];

  /// Stream origins at the top edge. Origins beyond the right edge enter the
  /// viewport as they descend, which fills the lower half without columns.
  static const _laneX = <double>[0.10, 0.37, 0.64, 0.91, 1.18, 1.45];
  static const _phases = <double>[0.00, 0.47, 0.19, 0.76, 0.34, 0.91];

  /// A stream moves for 64% of its cycle and rests for the remaining 36%.
  /// At the 24-second controller period this creates visible quiet intervals.
  static const _activeFraction = 0.64;

  /// A unit and the deliberately generous spacing between Morse marks.
  static const _unit = 8.0;
  static const _dot = _unit;
  static const _dash = _unit * 3;
  static const _symbolGap = _unit * 2.2;
  static const _letterGap = _unit * 5.2;
  static const _wordGap = _unit * 10.5;

  /// Short tails keep each mark meteor-like without joining neighbouring
  /// symbols into one continuous streak.
  static const _trailUnits = 4.5;
  static const _trailSteps = 3;

  /// Unit direction from upper-right to lower-left, about 20 degrees from
  /// vertical. Its length is effectively one, so distances remain intuitive.
  static const _direction = Offset(-0.34, 0.94);

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;

    final strokeWidth = math.max(1.8, size.shortestSide * 0.006);
    final head = Paint()
      ..strokeCap = StrokeCap.round
      ..strokeWidth = strokeWidth;
    final trail = Paint()
      ..strokeCap = StrokeCap.round
      ..strokeWidth = strokeWidth * 0.68;

    final marks = _sequence();
    final streamLength = marks.last.offset + marks.last.length + _wordGap;
    final screenDistance = size.height / _direction.dy;
    final travel = screenDistance + streamLength;

    for (var lane = 0; lane < _laneX.length; lane++) {
      final speed = 0.82 + (lane % 3) * 0.09;
      final cycle = (progress.value * speed + _phases[lane]) % 1.0;
      if (cycle >= _activeFraction) {
        continue; // the intentional pause between showers
      }

      final motion = cycle / _activeFraction;
      final leadDistance = motion * travel - streamLength;
      final originX = size.width * _laneX[lane];

      for (final mark in marks) {
        final distance = leadDistance + mark.offset;
        final start = Offset(
          originX + _direction.dx * distance,
          _direction.dy * distance,
        );
        final end = start + _direction * mark.length;

        if ((start.dy < -_wordGap && end.dy < -_wordGap) ||
            (start.dy > size.height + _wordGap &&
                end.dy > size.height + _wordGap) ||
            (start.dx < -_wordGap && end.dx < -_wordGap) ||
            (start.dx > size.width + _wordGap &&
                end.dx > size.width + _wordGap)) {
          continue;
        }

        final depth = (0.42 + 0.58 * (end.dy / size.height)).clamp(0.22, 1.0);
        final alpha = opacity * depth;

        head.color = color.withValues(alpha: alpha);
        canvas.drawLine(start, end, head);

        // Brighten only the leading tip along the same diagonal direction.
        head.color = color.withValues(alpha: (alpha * 1.8).clamp(0.0, 1.0));
        canvas.drawLine(end - _direction * (_unit * 0.35), end, head);

        final reach = _unit * _trailUnits;
        for (var step = 1; step <= _trailSteps; step++) {
          final from = start - _direction * (reach * step / _trailSteps);
          final to = start - _direction * (reach * (step - 1) / _trailSteps);
          trail.color = color.withValues(alpha: alpha * (0.52 / step));
          canvas.drawLine(from, to, trail);
        }
      }
    }
  }

  static List<_Mark> _sequence() {
    final marks = <_Mark>[];
    var offset = 0.0;
    for (var letterIndex = 0; letterIndex < _letters.length; letterIndex++) {
      final letter = _letters[letterIndex];
      if (letter == null) {
        offset += _wordGap - _symbolGap;
        continue;
      }
      if (letterIndex > 0 && _letters[letterIndex - 1] != null) {
        offset += _letterGap - _symbolGap;
      }
      for (final symbol in letter.split('')) {
        final length = symbol == '-' ? _dash : _dot;
        marks.add(_Mark(offset, length));
        offset += length + _symbolGap;
      }
    }
    return marks;
  }

  @override
  bool shouldRepaint(covariant _MorseMeteorPainter oldDelegate) =>
      oldDelegate.color != color || oldDelegate.opacity != opacity;
}

class _Mark {
  const _Mark(this.offset, this.length);

  final double offset;
  final double length;
}
