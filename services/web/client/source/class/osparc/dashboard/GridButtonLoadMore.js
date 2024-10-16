/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Study card to show that more studies are being fetched
 */

qx.Class.define("osparc.dashboard.GridButtonLoadMore", {
  extend: osparc.dashboard.GridButtonBase,

  construct: function() {
    this.base(arguments);

    this._applyFetching(false);
  },

  members: {
    checkIsOnScreen: function() {
      const isInViewport = element => {
        if (element) {
          const rect = element.getBoundingClientRect();
          const html = document.documentElement;
          return (
            rect.width > 0 &&
            rect.height > 0 &&
            rect.top >= 0 &&
            rect.left >= 0 &&
            // a bit of tolerance to deal with zooming factors
            rect.bottom*0.95 <= (window.innerHeight || html.clientHeight) &&
            rect.right*0.95 <= (window.innerWidth || html.clientWidth)
          );
        }
        return false;
      };

      const domElem = this.getContentElement().getDomElement();
      const checkIsOnScreen = isInViewport(domElem);
      return checkIsOnScreen;
    },

    _applyFetching: function(value) {
      const title = this.getChildControl("title");
      const desc = this.getChildControl("subtitle-text");
      if (value) {
        title.setValue(this.tr("Loading..."));
        desc.setValue("");
        this.setIcon(osparc.dashboard.CardBase.LOADING_ICON);
        this.getChildControl("icon").getChildControl("image").getContentElement()
          .addClass("rotate");
      } else {
        title.setValue(this.tr("Load More"));
        desc.setValue(this.tr("Click to load more").toString());
        this.setIcon("@FontAwesome5Solid/paw/");
        this.getChildControl("icon").getChildControl("image").getContentElement()
          .removeClass("rotate");
      }
      this.setEnabled(!value);
    },

    _onToggleChange: function(e) {
      this.setValue(false);
    },

    _shouldApplyFilter: function() {
      return false;
    },

    _shouldReactToFilter: function() {
      return false;
    }
  }
});
