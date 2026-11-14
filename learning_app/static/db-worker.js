import { PGlite } from "@electric-sql/pglite";
import { worker } from "@electric-sql/pglite/worker";

worker({
  async init(options) {
    const database = await PGlite.create(options);
    await database.exec("SET statement_timeout = '5s'");
    return database;
  },
});
