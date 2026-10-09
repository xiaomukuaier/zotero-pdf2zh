import assert from "node:assert/strict";
import test from "node:test";
import {
    ResultImports,
    isTrackedResult,
} from "../src/modules/pdf2zhResultImports.ts";

test("concurrent imports of the same result perform one operation", async () => {
    const imports = new ResultImports();
    let operations = 0;
    await Promise.all(
        Array.from({ length: 20 }, () =>
            imports.run("same-result", async () => {
                operations++;
                await new Promise((resolve) => setTimeout(resolve, 10));
            }),
        ),
    );
    assert.equal(operations, 1);
});

test("a rejected import can be retried", async () => {
    const imports = new ResultImports();
    await assert.rejects(
        imports.run("result", async () => {
            throw new Error("import failed");
        }),
    );
    let completed = false;
    await imports.run("result", async () => {
        completed = true;
    });
    assert.equal(completed, true);
});

test("persistent lookup applies to server job filenames", () => {
    assert.equal(
        isTrackedResult("e3dbf530-83b2-43e3-97ce-8295e220d33c_paper.dual.pdf"),
        true,
    );
    assert.equal(isTrackedResult("paper.dual.pdf"), false);
});
