package run.halo.mood;

import org.pf4j.PluginWrapper;
import run.halo.app.plugin.BasePlugin;

/**
 * 小窝心情 UC 入口插件。
 * 全部能力在前端 UI（ucRoutes 注册侧边栏菜单 + 跳转 /mood/ 独立页），
 * 后端不做任何事，仅作为插件载体存在。
 */
public class MoodPlugin extends BasePlugin {

    public MoodPlugin(PluginWrapper wrapper) {
        super(wrapper);
    }

    @Override
    public void start() {
        // nothing to do
    }

    @Override
    public void stop() {
        // nothing to do
    }
}
