import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { IoIosGlobe } from "react-icons/io";
import { useSelector, useDispatch } from "react-redux";
import { I18nKey } from "#/i18n/declaration";
import { RootState } from "#/store";
import { setUrl } from "#/state/browserSlice";

function Browser(): JSX.Element {
  const { t } = useTranslation();
  const dispatch = useDispatch();
  const { url, screenshotSrc } = useSelector(
    (state: RootState) => state.browser,
  );

  const [editableUrl, setEditableUrl] = useState(url);

  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setEditableUrl(e.target.value);
  };

  const handleUrlBlur = () => {
    dispatch(setUrl(editableUrl));
  };

  const imgSrc =
    screenshotSrc && screenshotSrc.startsWith("data:image/png;base64,")
      ? screenshotSrc
      : `data:image/png;base64,${screenshotSrc || ""}`;

  return (
    <div className="h-full w-full flex flex-col text-neutral-400">
      <div className="w-full p-2 truncate border-b border-neutral-600">
        <input
          type="text"
          value={editableUrl}
          onChange={handleUrlChange}
          onBlur={handleUrlBlur}
          className="w-full bg-transparent border-none outline-none text-neutral-400"
        />
      </div>
      <div className="overflow-y-auto grow scrollbar-hide rounded-xl">
        {screenshotSrc ? (
          <img
            src={imgSrc}
            style={{ objectFit: "contain", width: "100%", height: "auto" }}
            className="rounded-xl"
            alt="Browser Screenshot"
          />
        ) : (
          <div className="flex flex-col items-center h-full justify-center">
            <IoIosGlobe size={100} />
            {t(I18nKey.BROWSER$EMPTY_MESSAGE)}
          </div>
        )}
      </div>
    </div>
  );
}

export default Browser;
