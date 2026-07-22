# Product Spec

SFB is an offline production pipeline that converts clean canonical views or RGB/alpha/depth maps into lightweight 2.5D mobile assets. Splat input is an experimental future path, not part of the current MVP contract.

## Primary user

Technical artist or solo developer building stylized / semi-realistic mobile environments.

## Core promise

Use the best visible face of a controlled image or render, discard the unreliable 360° hallucination, and export a cheap mobile-ready facade.

## Non-goals

- 360° clean mesh reconstruction.
- Runtime splat renderer.
- MVP splat baking; `sfb bake-splat` is experimental and returns `not_implemented`.
- General-purpose level editor.
- General-purpose model training platform.
