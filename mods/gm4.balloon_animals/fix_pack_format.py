from beet import Context


def _sanitize(meta: dict) -> None:
    pack_meta = meta.setdefault("pack", {})
    pack_meta["pack_format"] = 15
    pack_meta.pop("supported_formats", None)
    pack_meta.pop("min_format", None)
    pack_meta.pop("max_format", None)


def beet_default(ctx: Context) -> None:
    if ctx.data.mcmeta:
        _sanitize(ctx.data.mcmeta.data)
    if ctx.assets and ctx.assets.mcmeta:
        _sanitize(ctx.assets.mcmeta.data)
    for pack in ctx.packs:
        if pack.mcmeta:
            _sanitize(pack.mcmeta.data)
