/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Widget that displays the main view of a node.
 * - On the left side shows the default inputs if any and also what the input nodes offer
 * - In the center the content of the node: settings, mapper, iframe...
 *
 * When a node is set the layout is built
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let nodeView = new osparc.component.node.NodeView();
 *   nodeView.setNode(workbench.getNode1());
 *   nodeView.populateLayout();
 *   this.getRoot().add(nodeView);
 * </pre>
 */

qx.Class.define("osparc.component.node.NodeView", {
  extend: osparc.component.node.BaseNodeView,

  statics: {
    isPropsFormShowable: function(node) {
      if (node && ("getPropsForm" in node) && node.getPropsForm()) {
        return node.getPropsForm().hasVisibleInputs();
      }
      return false;
    }
  },

  members: {
    _addSettings: function() {
      this._settingsLayout.removeAll();
      this._mapperLayout.removeAll();

      const node = this.getNode();
      const propsForm = node.getPropsForm();
      if (propsForm && Object.keys(node.getInputs()).length) {
        propsForm.addListener("changeChildVisibility", () => {
          this.__checkSettingsVisibility();
        }, this);
        this._settingsLayout.add(propsForm);
      }
      this.__checkSettingsVisibility();
      const mapper = node.getInputsMapper();
      if (mapper) {
        this._mapperLayout.add(mapper, {
          flex: 1
        });
      }

      this._addToMainView(this._settingsLayout);
      this._addToMainView(this._mapperLayout, {
        flex: 1
      });
    },

    __checkSettingsVisibility: function() {
      const isSettingsGroupShowable = this.isSettingsGroupShowable();
      this._settingsLayout.setVisibility(isSettingsGroupShowable ? "visible" : "excluded");
    },

    isSettingsGroupShowable: function() {
      const node = this.getNode();
      return this.self().isPropsFormShowable(node);
    },

    __iFrameChanged: function() {
      this._iFrameLayout.removeAll();

      const loadingPage = this.getNode().getLoadingPage();
      const iFrame = this.getNode().getIFrame();
      const src = iFrame.getSource();
      const iFrameView = (src === null || src === "about:blank") ? loadingPage : iFrame;
      this._iFrameLayout.add(iFrameView, {
        flex: 1
      });
    },

    _addIFrame: function() {
      this._iFrameLayout.removeAll();

      const loadingPage = this.getNode().getLoadingPage();
      const iFrame = this.getNode().getIFrame();
      if (loadingPage === null && iFrame === null) {
        return;
      }
      [
        loadingPage,
        iFrame
      ].forEach(widget => {
        if (widget) {
          widget.addListener("maximize", e => {
            this._maximizeIFrame(true);
          }, this);
          widget.addListener("restore", e => {
            this._maximizeIFrame(false);
          }, this);
          this._maximizeIFrame(widget.hasState("maximized"));
        }
      });
      this.__iFrameChanged();

      iFrame.addListener("load", () => {
        this.__iFrameChanged();
      });

      this._addToMainView(this._iFrameLayout, {
        flex: 1
      });
    },

    _openEditAccessLevel: function() {
      const settingsEditorLayout = osparc.component.node.BaseNodeView.createSettingsGroupBox(this.tr("Settings"));
      const propsFormEditor = this.getNode().getPropsFormEditor();
      settingsEditorLayout.add(propsFormEditor);
      const title = this.getNode().getLabel();
      osparc.ui.window.Window.popUpInWindow(settingsEditorLayout, title, 800, 600).set({
        autoDestroy: false
      });
    },

    _applyNode: function(node) {
      if (node.isContainer()) {
        console.error("Only non-group nodes are supported");
      }
      this.base(arguments, node);
    }
  }
});
