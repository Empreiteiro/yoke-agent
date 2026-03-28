"use client";

import { useState, useCallback } from "react";
import { Upload, FileText, X, CheckCircle, AlertCircle, FolderOpen } from "lucide-react";
import { api } from "@/lib/api";
import { formatBytes } from "@/lib/utils";

interface StepUploadProps {
  onComplete: (documentIds: number[]) => void;
}

export default function StepUpload({ onComplete }: StepUploadProps) {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploaded, setUploaded] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const ACCEPTED_EXTENSIONS = [".pdf", ".txt", ".docx", ".md", ".mdx", ".csv"];

  const isAcceptedFile = (name: string) =>
    ACCEPTED_EXTENSIONS.some((ext) => name.toLowerCase().endsWith(ext));

  const readDirectoryEntries = async (dirEntry: FileSystemDirectoryEntry): Promise<File[]> => {
    const reader = dirEntry.createReader();
    const files: File[] = [];
    const readBatch = (): Promise<FileSystemEntry[]> =>
      new Promise((resolve) => reader.readEntries(resolve));

    let entries = await readBatch();
    while (entries.length > 0) {
      for (const entry of entries) {
        if (entry.isFile) {
          const file = await new Promise<File>((resolve) =>
            (entry as FileSystemFileEntry).file(resolve)
          );
          if (isAcceptedFile(file.name)) files.push(file);
        } else if (entry.isDirectory) {
          const subFiles = await readDirectoryEntries(entry as FileSystemDirectoryEntry);
          files.push(...subFiles);
        }
      }
      entries = await readBatch();
    }
    return files;
  };

  const handleDrop = useCallback(async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const items = Array.from(e.dataTransfer.items);
    const allFiles: File[] = [];

    for (const item of items) {
      const entry = item.webkitGetAsEntry?.();
      if (entry?.isDirectory) {
        const dirFiles = await readDirectoryEntries(entry as FileSystemDirectoryEntry);
        allFiles.push(...dirFiles);
      } else if (entry?.isFile) {
        const file = await new Promise<File>((resolve) =>
          (entry as FileSystemFileEntry).file(resolve)
        );
        if (isAcceptedFile(file.name)) allFiles.push(file);
      }
    }

    if (allFiles.length > 0) {
      setFiles((prev) => [...prev, ...allFiles]);
    }
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selected = Array.from(e.target.files).filter((f) => isAcceptedFile(f.name));
      setFiles((prev) => [...prev, ...selected]);
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    setError(null);

    try {
      const result = await api.uploadDocuments(files);
      setUploaded(result);
      setFiles([]);
    } catch (err: any) {
      setError(err.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleContinue = () => {
    onComplete(uploaded.map((d: any) => d.id));
  };

  return (
    <div className="space-y-6">
      <div className="bg-surface-100 rounded-2xl border border-surface-200/50 p-8">
        {/* Drop zone */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-xl p-12 text-center transition-all ${
            dragActive
              ? "border-accent bg-accent/5"
              : "border-surface-300 hover:border-accent/50"
          }`}
        >
          <Upload className="w-12 h-12 text-muted mx-auto mb-4" />
          <p className="text-sm text-t-hover mb-3">
            Drag and drop files or folders here
          </p>
          <div className="flex items-center justify-center gap-3 mb-3">
            <label className="flex items-center gap-1.5 px-4 py-2 bg-accent/10 text-accent text-sm font-medium rounded-lg cursor-pointer hover:bg-accent/20 transition-colors">
              <FileText className="w-4 h-4" />
              Select Files
              <input
                type="file"
                multiple
                onChange={handleFileSelect}
                className="hidden"
                accept=".pdf,.txt,.docx,.md,.mdx,.csv"
              />
            </label>
            <label className="flex items-center gap-1.5 px-4 py-2 bg-secondary/10 text-secondary text-sm font-medium rounded-lg cursor-pointer hover:bg-secondary/20 transition-colors">
              <FolderOpen className="w-4 h-4" />
              Select Folder
              {/* @ts-ignore — webkitdirectory is non-standard but widely supported */}
              <input
                type="file"
                onChange={handleFileSelect}
                className="hidden"
                {...({ webkitdirectory: "", directory: "" } as any)}
              />
            </label>
          </div>
          <p className="text-xs text-muted">
            PDF, TXT, DOCX, MD, CSV up to 50MB each
          </p>
        </div>

        {/* File list */}
        {files.length > 0 && (
          <div className="mt-6 space-y-2">
            {files.map((file, index) => (
              <div
                key={index}
                className="flex items-center justify-between px-4 py-3 bg-surface-50 rounded-xl border border-surface-200/50"
              >
                <div className="flex items-center gap-3">
                  <FileText className="w-5 h-5 text-accent" />
                  <div>
                    <p className="text-sm text-primary">{file.name}</p>
                    <p className="text-xs text-muted">
                      {formatBytes(file.size)}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => removeFile(index)}
                  className="p-1 hover:bg-surface-200 rounded-lg transition-colors"
                >
                  <X className="w-4 h-4 text-t-secondary" />
                </button>
              </div>
            ))}

            <button
              onClick={handleUpload}
              disabled={uploading}
              className="mt-4 w-full py-3 px-6 bg-gradient-to-r from-accent to-accent-dark text-primary font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {uploading ? "Uploading..." : `Upload ${files.length} file(s)`}
            </button>
          </div>
        )}

        {error && (
          <div className="mt-4 flex items-center gap-2 text-red-400 text-sm">
            <AlertCircle className="w-4 h-4" />
            {error}
          </div>
        )}
      </div>

      {/* Uploaded documents */}
      {uploaded.length > 0 && (
        <div className="bg-surface-100 rounded-2xl border border-emerald-500/20 p-8">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle className="w-5 h-5 text-emerald-400" />
            <h3 className="text-lg font-semibold text-primary">
              Documents Uploaded
            </h3>
          </div>
          <div className="space-y-2 mb-6">
            {uploaded.map((doc: any) => (
              <div
                key={doc.id}
                className="flex items-center gap-3 px-4 py-3 bg-surface-50 rounded-xl"
              >
                <FileText className="w-5 h-5 text-emerald-400" />
                <span className="text-sm text-primary">{doc.filename}</span>
                <span className="text-xs text-muted ml-auto">
                  {formatBytes(doc.file_size)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {uploaded.length > 0 && (
        <button
          onClick={handleContinue}
          className="w-full py-3 px-6 bg-gradient-to-r from-accent to-accent-dark text-primary font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
        >
          Continue to Dataset Generation
        </button>
      )}
    </div>
  );
}
