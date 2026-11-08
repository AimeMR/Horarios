process.stdout.write(JSON.stringify({ cwd: process.cwd(), value: process.env.PROC_TEST_VAR ?? null }));
