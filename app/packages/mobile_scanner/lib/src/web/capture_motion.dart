/// Conservative directional-motion screening, not a QR safety verdict.
/// Uses native-pixel adjacent gradients so downsampling cannot hide streaks.
double directionalDetailRatio(List<int> rgba, int width, int height) {
  if (width < 8 || height < 8 || rgba.length < width * height * 4) return 0;
  double luminance(int x, int y) {
    final i = (y * width + x) * 4;
    return .299 * rgba[i] + .587 * rgba[i + 1] + .114 * rgba[i + 2];
  }

  var horizontal = 0.0;
  var vertical = 0.0;
  // Ignore outer paper/viewer edges; retain module detail across the symbol.
  for (var y = height ~/ 5; y < height * 4 ~/ 5 - 1; y += 3) {
    for (var x = width ~/ 5; x < width * 4 ~/ 5 - 1; x += 3) {
      final centre = luminance(x, y);
      final dx = luminance(x + 1, y) - centre;
      final dy = luminance(x, y + 1) - centre;
      horizontal += dx * dx;
      vertical += dy * dy;
    }
  }
  final high = horizontal > vertical ? horizontal : vertical;
  final low = horizontal < vertical ? horizontal : vertical;
  return high <= 0 ? 0 : low / high;
}
