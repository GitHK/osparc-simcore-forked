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
 * @ignore(URL)
 * @ignore(sessionStorage)
 * @ignore(fetch)
 * @ignore(URLSearchParams)
 */

/**
 * Sandbox of static methods that do not fit in other utils classes.
 */

qx.Class.define("osparc.utils.Utils", {
  type: "static",

  statics: {
    computeServiceUrl: function(resp) {
      const data = {
        srvUrl: null,
        isDynamicV2: null
      };
      const isDynamicV2 = resp["boot_type"] === "V2" || false;
      data["isDynamicV2"] = isDynamicV2;
      if (isDynamicV2) {
        // dynamic service
        const srvUrl = window.location.protocol + "//" + resp["service_uuid"] + ".services." + window.location.host;
        data["srvUrl"] = srvUrl;
      } else {
        // old implementation
        const servicePath = resp["service_basepath"];
        const entryPointD = resp["entry_point"];
        if (servicePath) {
          const entryPoint = entryPointD ? ("/" + entryPointD) : "/";
          const srvUrl = servicePath + entryPoint;
          data["srvUrl"] = srvUrl;
        }
      }
      return data;
    },

    computeServiceRetrieveUrl: function(srvUrl, isDynamicV2 = false) {
      let urlRetrieve = null;
      if (isDynamicV2) {
        urlRetrieve = srvUrl + ":retrieve";
        urlRetrieve = urlRetrieve.replace("/:retrieve", ":retrieve");
      } else {
        urlRetrieve = srvUrl + "/retrieve";
        urlRetrieve = urlRetrieve.replace("//retrieve", "/retrieve");
      }
      return urlRetrieve;
    },

    isDevelopmentPlatform: function() {
      return new Promise((resolve, reject) => {
        osparc.utils.LibVersions.getPlatformName()
          .then(platformName => {
            if (["dev", "master"].includes(platformName)) {
              resolve(true);
            } else {
              resolve(false);
            }
          });
      });
    },

    getEditButton: function() {
      const button = new qx.ui.form.Button(null, "@FontAwesome5Solid/pencil-alt/12").set({
        allowGrowY: false,
        padding: 3,
        maxWidth: 20
      });
      return button;
    },

    getViewButton: function() {
      const button = new qx.ui.form.Button(null, "@FontAwesome5Solid/eye/12").set({
        allowGrowY: false,
        padding: 3,
        maxWidth: 20
      });
      return button;
    },

    getCopyButton: function() {
      const button = new qx.ui.form.Button(null, "@FontAwesome5Solid/copy/12").set({
        allowGrowY: false,
        padding: 3,
        maxWidth: 20
      });
      return button;
    },

    /**
      * @param value {Date Object} Date Object
      */
    formatDate: function(value) {
      // create a date format like "Oct. 19, 2018 11:31 AM"
      const dateFormat = new qx.util.format.DateFormat(
        qx.locale.Date.getDateFormat("medium")
      );

      let dateStr = null;
      if (value.getDate() === (new Date()).getDate()) {
        dateStr = qx.locale.Manager.tr("Today");
      } else if (value.getDate() === (new Date()).getDate() - 1) {
        dateStr = qx.locale.Manager.tr("Yesterday");
      } else {
        dateStr = dateFormat.format(value);
      }
      return dateStr;
    },

    /**
      * @param value {Date Object} Date Object
      */
    formatTime: function(value) {
      const timeFormat = new qx.util.format.DateFormat(
        qx.locale.Date.getTimeFormat("short")
      );
      const timeStr = timeFormat.format(value);
      return timeStr;
    },

    /**
      * @param value {Date Object} Date Object
      */
    formatDateAndTime: function(value) {
      return osparc.utils.Utils.formatDate(value) + " " + osparc.utils.Utils.formatTime(value);
    },

    getNameFromEmail: function(email) {
      return email.split("@")[0];
    },

    uuidv4: function() {
      return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
        (c ^ window.crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16));
    },

    isInZ43: function() {
      return window.location.hostname.includes("speag");
    },

    getLogoPath: function() {
      let logoPath = null;
      const product = qx.core.Environment.get("product.name");
      switch (product) {
        case "s4l":
          logoPath = "osparc/s4l_logo.png";
          break;
        case "tis":
          logoPath = "osparc/ti-tp.svg";
          break;
        default: {
          const colorManager = qx.theme.manager.Color.getInstance();
          const textColor = colorManager.resolve("text");
          const luminance = this.getColorLuminance(textColor);
          logoPath = (luminance > 0.3) ? "osparc/osparc-white.svg" : "osparc/osparc-black.svg";
          break;
        }
      }
      return logoPath;
    },

    addBorder: function(sidePanel, width = 1, where = "right") {
      sidePanel.getContentElement().setStyle("border-"+where, width+"px solid " + qx.theme.manager.Color.getInstance().resolve("material-button-background"));
    },

    __setStyleToIFrame: function(domEl) {
      if (domEl && domEl.contentDocument && domEl.contentDocument.documentElement) {
        const iframeDocument = domEl.contentDocument.documentElement;
        const colorManager = qx.theme.manager.Color.getInstance();
        const bgColor = colorManager.resolve("loading-page-background-color");
        const textColor = colorManager.resolve("loading-page-text");
        const spinnerColor = colorManager.resolve("loading-page-spinner");
        iframeDocument.style.setProperty("--background-color", bgColor);
        iframeDocument.style.setProperty("--text-color", textColor);
        iframeDocument.style.setProperty("--spinner-color", spinnerColor);
      }
    },

    compareVersionNumbers: function(v1, v2) {
      // https://stackoverflow.com/questions/6832596/how-to-compare-software-version-number-using-js-only-number/47500834
      // - a number < 0 if a < b
      // - a number > 0 if a > b
      // - 0 if a = b
      const regExStrip0 = /(\.0+)+$/;
      const segmentsA = v1.replace(regExStrip0, "").split(".");
      const segmentsB = v2.replace(regExStrip0, "").split(".");
      const l = Math.min(segmentsA.length, segmentsB.length);

      for (let i = 0; i < l; i++) {
        const diff = parseInt(segmentsA[i], 10) - parseInt(segmentsB[i], 10);
        if (diff) {
          return diff;
        }
      }
      return segmentsA.length - segmentsB.length;
    },

    // deep clone of nested objects
    deepCloneObject: function(src) {
      return JSON.parse(JSON.stringify(src));
    },

    getRandomColor: function() {
      let letters = "0123456789ABCDEF";
      let color = "#";
      for (let i = 0; i < 6; i++) {
        color += letters[Math.floor(Math.random() * 16)];
      }
      return color;
    },

    getColorLuminance: function(hexColor) {
      const rgb = qx.util.ColorUtil.hexStringToRgb(hexColor);
      const luminance = 0.2126*(rgb[0]/255) + 0.7152*(rgb[1]/255) + 0.0722*(rgb[2]/255);
      return luminance;
    },

    getContrastedTextColor: function(hexColor) {
      const L = this.getColorLuminance(hexColor);
      return L > 0.35 ? "contrasted-text-dark" : "contrasted-text-light";
    },

    bytesToSize: function(bytes) {
      const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
      if (bytes == 0) {
        return "0 Bytes";
      }
      const i = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)));
      return Math.round(bytes / Math.pow(1024, i), 2) + " " + sizes[i];
    },

    retrieveURLAndDownload: function(locationId, fileId) {
      let fileName = fileId.split("/");
      fileName = fileName[fileName.length-1];
      const download = true;
      const dataStore = osparc.store.Data.getInstance();
      dataStore.getPresignedLink(download, locationId, fileId)
        .then(presignedLinkData => {
          if (presignedLinkData.presignedLink) {
            const link = presignedLinkData.presignedLink.link;
            const fileNameFromLink = this.fileNameFromPresignedLink(link);
            fileName = fileNameFromLink ? fileNameFromLink : fileName;
            this.downloadLink(link, "GET", fileName);
          }
        });
    },

    downloadLink: function(url, method, fileName, downloadStartedCB) {
      return new Promise((resolve, reject) => {
        let xhr = new XMLHttpRequest();
        xhr.open(method, url, true);
        xhr.responseType = "blob";
        xhr.addEventListener("readystatechange", () => {
        // xhr.onreadystatechange = () => {
          if (xhr.readyState === XMLHttpRequest.HEADERS_RECEIVED) {
            // The responseType value can be changed at any time before the readyState reaches 3.
            // When the readyState reaches 2, we have access to the response headers to make that decision with.
            if (xhr.status >= 200 && xhr.status < 400) {
              xhr.responseType = "blob";
            } else {
              // get ready for handling an error
              xhr.responseType = "text";
            }
          }
        });
        xhr.addEventListener("progress", () => {
          if (xhr.readyState === XMLHttpRequest.LOADING) {
            if (xhr.status === 0 || (xhr.status >= 200 && xhr.status < 400)) {
              if (downloadStartedCB) {
                downloadStartedCB();
              }
            }
          }
        });
        xhr.addEventListener("load", () => {
          if (xhr.status == 200) {
            let blob = new Blob([xhr.response]);
            let urlBlob = window.URL.createObjectURL(blob);
            let downloadAnchorNode = document.createElement("a");
            downloadAnchorNode.setAttribute("href", urlBlob);
            if (!fileName) {
              fileName = this.self().filenameFromContentDisposition(xhr);
            }
            downloadAnchorNode.setAttribute("download", fileName);
            downloadAnchorNode.click();
            downloadAnchorNode.remove();
            resolve();
          } else {
            reject(xhr);
          }
        });
        xhr.addEventListener("error", () => reject(xhr));
        xhr.addEventListener("abort", () => reject(xhr));
        xhr.send();
      });
    },

    filenameFromContentDisposition: function(xhr) {
      // https://stackoverflow.com/questions/40939380/how-to-get-file-name-from-content-disposition
      let filename = "";
      const disposition = xhr.getResponseHeader("Content-Disposition");
      if (disposition && disposition.indexOf("attachment") !== -1) {
        const filenameRegex = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/;
        const matches = filenameRegex.exec(disposition);
        if (matches != null && matches[1]) {
          filename = matches[1].replace(/['"]/g, "");
        }
      }
      return filename;
    },

    fileNameFromPresignedLink: function(link) {
      // regex match /([^/]+)\?
      const fileNames = new URL(link).pathname.split("/");
      if (fileNames.length) {
        return fileNames.pop();
      }
      return null;
    },

    /**
     * Function that takes an indefinite number of strings as separated parameters, and concatenates them capitalizing the first letter.
     */
    capitalize: function() {
      let res = "";
      for (let i=0; i<arguments.length; i++) {
        if (typeof arguments[i] !== "string" && arguments[i] instanceof String === false) {
          continue;
        }
        const capitalized = arguments[i].charAt(0).toUpperCase() + arguments[i].slice(1);
        res = res.concat(capitalized);
      }
      return res;
    },

    /**
     * Copies the given text to the clipboard
     *
     * @param text {String} Text to be copied
     * @return {Boolean} True if it was successful
     */
    copyTextToClipboard: function(text) {
      // from https://stackoverflow.com/questions/400212/how-do-i-copy-to-the-clipboard-in-javascript
      const textArea = document.createElement("textarea");

      //
      // *** This styling is an extra step which is likely not required. ***
      //
      // Why is it here? To ensure:
      // 1. the element is able to have focus and selection.
      // 2. if element was to flash render it has minimal visual impact.
      // 3. less flakyness with selection and copying which **might** occur if
      //    the textarea element is not visible.
      //
      // The likelihood is the element won't even render, not even a
      // flash, so some of these are just precautions. However in
      // Internet Explorer the element is visible whilst the popup
      // box asking the user for permission for the web page to
      // copy to the clipboard.
      //

      // Place in top-left corner of screen regardless of scroll position.
      // Ensure it has a small width and height. Setting to 1px / 1em
      // doesn't work as this gives a negative w/h on some browsers.
      // We don't need padding, reducing the size if it does flash render.
      // Clean up any borders.
      // Avoid flash of white box if rendered for any reason.
      textArea.style = {
        position: "fixed",
        top: 0,
        left: 0,
        width: "2em",
        height: "2em",
        padding: 0,
        border: "none",
        outline: "none",
        boxShadow: "none",
        background: "transparent"
      };
      textArea.value = text;

      document.body.appendChild(textArea);
      textArea.focus();
      textArea.select();

      let copied = false;
      try {
        copied = document.execCommand("copy");
      } catch (err) {
        console.error("Oops, unable to copy");
      }

      document.body.removeChild(textArea);

      return copied;
    },

    cookie: {
      setCookie: (cname, cvalue, exdays) => {
        var d = new Date();
        d.setTime(d.getTime() + (exdays * 24 * 60 * 60 * 1000));
        var expires = "expires="+d.toUTCString();
        document.cookie = cname + "=" + cvalue + ";" + expires + ";path=/";
      },

      getCookie: cname => {
        const name = cname + "=";
        const ca = document.cookie.split(";");
        for (let i = 0; i < ca.length; i++) {
          let c = ca[i];
          while (c.charAt(0) == " ") {
            c = c.substring(1);
          }
          if (c.indexOf(name) == 0) {
            return c.substring(name.length, c.length);
          }
        }
        return null;
      },

      deleteCookie: cname => {
        document.cookie = cname + "=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
      }
    },

    parseURLFragment: () => {
      let urlHash = window.location.hash.slice(1);
      const parsedFragment = {};
      if (urlHash.length) {
        urlHash = urlHash.split("?");
        if (urlHash.length < 3) {
          // Nav
          urlHash[0].split("/").forEach(fragmentPart => {
            if (fragmentPart.length) {
              parsedFragment.nav = parsedFragment.nav || [];
              parsedFragment.nav.push(decodeURIComponent(fragmentPart));
            }
          });
          if (urlHash.length === 2) {
            // Params
            parsedFragment.params = parsedFragment.params || {};
            urlHash[1].replace(/([^=&]+)=([^&]*)/g, function(m, key, value) {
              parsedFragment.params[decodeURIComponent(key)] = decodeURIComponent(value);
            });
          }
        } else {
          console.error("URL fragment doesn't have the correct format.");
          return null;
        }
      }
      return parsedFragment;
    },

    getParamFromURL: (url, param) => {
      const urlParams = new URLSearchParams(url);
      return urlParams.get(param);
    },

    hasParamFromURL: (url, param) => {
      const urlParams = new URLSearchParams(url);
      return urlParams.has(param);
    },

    getThumbnailFromUuid: uuid => {
      const lastCharacters = uuid.substr(uuid.length-10);
      const aNumber = parseInt(lastCharacters, 16);
      const thumbnailId = aNumber%25;
      return "osparc/img"+ thumbnailId +".jpg";
    },

    getThumbnailFromString: str => "osparc/img" + Math.abs(this.self().stringHash(str)%25) + ".jpg",

    stringHash: str => {
      // Based on https://stackoverflow.com/questions/7616461/generate-a-hash-from-string-in-javascript
      let hash = 0;
      let i;
      let chr;
      if (str.length === 0) {
        return hash;
      }
      for (i=0; i<str.length; i++) {
        chr = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + chr;
        hash |= 0; // Convert to 32bit integer
      }
      return hash;
    },

    isUrl: url => /^(http:\/\/www\.|https:\/\/www\.|http:\/\/|https:\/\/)?[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?$/gm.test(url),

    setIdToWidget: (qWidget, id) => {
      if (qWidget.getContentElement) {
        qWidget.getContentElement().setAttribute("osparc-test-id", id);
      }
    },

    getClientSessionID: function() {
      // https://stackoverflow.com/questions/11896160/any-way-to-identify-browser-tab-in-javascript
      const clientSessionID = sessionStorage.getItem("clientsessionid") ? sessionStorage.getItem("clientsessionid") : osparc.utils.Utils.uuidv4();
      sessionStorage.setItem("clientsessionid", clientSessionID);
      return clientSessionID;
    },

    getFreeDistanceToWindowEdges: function(layoutItem) {
      const domElement = layoutItem.getContentElement().getDomElement();
      if (domElement === null) {
        return null;
      }
      const location = qx.bom.element.Location.get(domElement);
      return {
        top: location.top,
        right: window.innerWidth - location.right,
        bottom: window.innerHeight - location.bottom,
        left: location.left
      };
    },

    fetchJSON: function() {
      return fetch.apply(null, arguments).then(response => response.json());
    },

    firstsUp: function(...args) {
      const labels = [];
      args.forEach(arg => labels.push(qx.lang.String.firstUp(arg)));
      return labels.join(" ");
    },

    isObject: function(v) {
      return typeof v === "object" && v !== null;
    }
  }
});
