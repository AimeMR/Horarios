const total = Number(process.argv[2]);
process.stdout.write("SECRETFLOOD".repeat(Math.ceil(total / 11)).slice(0, total));
