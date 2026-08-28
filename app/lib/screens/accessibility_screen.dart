/// Motion and contrast controls that complement system accessibility settings.
library;

import 'package:flutter/material.dart';

import '../app_controller.dart';
import '../theme.dart';
import 'settings_screen.dart';

class AccessibilityScreen extends StatelessWidget {
  const AccessibilityScreen({super.key, required this.appController});

  final AppController appController;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Accessibility')),
    body: AnimatedBuilder(
      animation: appController,
      builder: (context, _) {
        final systemAnimationsDisabled = MediaQuery.of(
          context,
        ).disableAnimations;
        return ListView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
          children: [
            const SettingsBrandHeader(
              title: 'Comfort and Clarity',
              body:
                  'Verdicts always use an icon and a word as well as colour. '
                  'These controls reduce non-essential visual movement.',
            ),
            const SizedBox(height: 24),
            Card(
              child: Column(
                children: [
                  SwitchListTile(
                    value: appController.reduceMotion,
                    onChanged: appController.setReduceMotion,
                    secondary: Icon(
                      Icons.motion_photos_off_outlined,
                      color: context.qrColors.brandInk,
                    ),
                    title: const Text(
                      'Reduce Motion',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    subtitle: const Text(
                      'Render Morse signals statically and avoid non-essential '
                      'score or stage animation.',
                    ),
                  ),
                  const Divider(height: 1),
                  SwitchListTile(
                    value: appController.enhancedContrast,
                    onChanged: appController.setEnhancedContrast,
                    secondary: Icon(
                      Icons.contrast_rounded,
                      color: context.qrColors.brandInk,
                    ),
                    title: const Text(
                      'Enhanced Contrast',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    subtitle: const Text(
                      'Strengthen borders and technical background visibility.',
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Icon(
                      systemAnimationsDisabled
                          ? Icons.check_circle_outline_rounded
                          : Icons.settings_outlined,
                      color: systemAnimationsDisabled
                          ? context.qrColors.safe
                          : context.qrColors.secondaryText,
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            systemAnimationsDisabled
                                ? 'System motion reduction is active'
                                : 'System motion preference is respected',
                            style: const TextStyle(fontWeight: FontWeight.w700),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'The system preference overrides QRGuard motion. '
                            'System text scaling is also applied throughout the app.',
                            style: TextStyle(
                              color: context.qrColors.secondaryText,
                              height: 1.4,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        );
      },
    ),
  );
}
