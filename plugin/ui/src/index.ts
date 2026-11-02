import { definePlugin } from "@halo-dev/ui-shared";
import MoodView from "./views/MoodView.vue";

export default definePlugin({
  components: {},
  routes: [],
  ucRoutes: [
    {
      parentName: "Root",
      route: {
        path: "/mood",
        name: "SamHouseMood",
        component: MoodView,
        meta: {
          title: "小窝心情",
          searchable: false,
          menu: {
            name: "小窝心情",
            priority: 45,
          },
        },
      },
    },
  ],
  extensionPoints: {},
});
