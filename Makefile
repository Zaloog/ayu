.PHONY: all
MAKE               := make --no-print-directory
RUN 			   := uv run
VERSION            := v$(shell uv version --short)


release:
	git tag $(VERSION)
	git push origin $(VERSION)

notes:
	# Thanks Will
	gh release create --generate-notes $(VERSION)
