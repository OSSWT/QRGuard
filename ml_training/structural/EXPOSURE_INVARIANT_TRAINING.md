# Exposure-invariant Structural training contract

This contract addresses exposure as a nuisance variable, not a Structural label.
An overexposed or underexposed frame must never be called clean or manipulated
because of exposure alone.

## Training evidence

1. Lock the parent split by base QR, payload, capture session, device and display.
2. Reject severe/unusable crops through the acquisition quality gate.
3. Pair only rows with the same Structural class and `paired_group`. A temporal
   partner is preferred; a second view of the same image is the safe fallback.
4. Apply moderate random exposure (-0.75 to +0.75 EV), contrast (0.8 to 1.2), and
   gamma (0.8 to 1.25) to the partner view.
5. Train both views with the same ground-truth class and add symmetric KL
   consistency loss at weight 0.20.

No label is inferred from successful decoding, brightness, QR version, mask, or
payload length. Physical adversarial rows additionally require an explicit
`physical_attack_survival_verified=true` audit result.

## Checkpoint selection and promotion

Every checkpoint is scored on global macro-F1, deployment-domain macro-F1,
Gallery/Camera agreement, and a deterministic exposure sweep. The final candidate
is evaluated at -0.67, 0, and +0.67 EV.

Required exposure gates:

- binary clean/manipulated verdict agreement across the sweep: at least 0.95;
- clean `p_structural` exposure span P95: at most 0.15;
- no automatic runtime promotion;
- a fresh blinded holdout using unseen QR identities and a new
  device/display/session combination remains mandatory.

Public QR localization or camera-noise datasets can improve acquisition, but they
cannot satisfy the physical Structural attack gate. The latter requires QRGuard's
own verified, post-capture evidence.
