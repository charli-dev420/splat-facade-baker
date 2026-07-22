# View Adapter Plan

The view adapter will learn:

```text
source image + target_view_id + target camera metadata → target image
```

The angle is provided by `ViewContract`; it is never guessed by the model. The
View Adapter remains a plan until a real runner, dataset and evaluation loop are
validated. No public placeholder backend or runnable demo config is shipped for
this path.
