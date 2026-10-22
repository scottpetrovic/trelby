#!/bin/bash
xgettext -j -L Python -o po/trelby.pot \
	--package-name=trelby \
        --package-version=3.0.0.0 \
        --copyright-holder="Gwyn Ciesla <gwync@protonmail.com>" \
	$(find ./trelby -type f -name '*.py')
