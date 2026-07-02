<!--
Copyright: Ankitects Pty Ltd and contributors
Copyright: TopGRE contributors
License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
-->
<script lang="ts">
    import type { PageData } from "./$types";
    import ReadinessPage from "./ReadinessPage.svelte";

    export let data: PageData;
</script>

<ReadinessPage info={data.info} />
