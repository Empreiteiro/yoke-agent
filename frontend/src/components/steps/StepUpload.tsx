"use client";

import { useState, useCallback } from "react";
import { Upload, FileText, X, CheckCircle, AlertCircle } from "lucide-react";
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

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    setFiles((prev) => [...prev, ...droppedFiles]);
  }, []);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles((prev) => [...prev, ...Array.from(e.target.files!)]);
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
          <p className="text-sm text-t-hover mb-2">
            Drag and drop files here, or{" "}
            <label className="text-accent cursor-pointer hover:underline">
              browse
              <input
                type="file"
                multiple
                onChange={handleFileSelect}
                className="hidden"
                accept=".pdf,.txt,.docx,.md,.csv"
              />
            </label>
          </p>
          <p className="text-xs text-muted">
            PDF, TXT, DOCX, MD up to 50MB each
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
              className="mt-4 w-full py-3 px-6 bg-gradient-to-r from-accent to-accent-dark text-primary font-medium rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50"
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
          <button
            onClick={handleContinue}
            className="w-full py-3 px-6 bg-gradient-to-r from-emerald-500 to-emerald-600 text-primary font-medium rounded-xl hover:opacity-90 transition-opacity"
          >
            Continue to Dataset Generation
          </button>
        </div>
      )}
    </div>
  );
}
