// Copyright: Ankitects Pty Ltd and contributors
// Copyright: TopGRE contributors
// License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
import { getReadiness } from "@generated/backend";

import type { PageLoad } from "./$types";

export const load = (async () => {
    const info = await getReadiness({ search: "" });
    return { info };
}) satisfies PageLoad;
