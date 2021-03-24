#include "DistanceMethods.hpp"

#ifdef USE_PHYDSTAR

#include "phylokit/newick.hpp"
#include "jni.h"
#include "whereami.h"
#include <fstream>


std::string mydir() {
  int length = wai_getExecutablePath(NULL, 0, NULL);
  int dirname_length;
  char* path = (char*)malloc(length + 1);
  wai_getExecutablePath(path, length, &dirname_length);
  path[dirname_length] = '\0';
  std::string dir(path);
  free(path);
  return dir;
}

void write_matrix(TaxonSet& ts, DistanceMatrix& dm, std::ostream& os) {
  os << ts.size() << std::endl;
  for (size_t i = 0; i < ts.size(); i++) {
    os << i << " ";
    for (size_t j = 0; j < ts.size(); j++) {
      if (i == j) {
	os << "0.0 ";
      }
      else if (dm.has(i, j)) 
	os << dm(i, j) << " ";
      else
	os << "-99.0 ";
    }
    os << "\n";
  }
}

void runPhyDStar(std::string method, std::string tempfilename, std::vector<std::string>& java_opts) {
  JavaVM *jvm;       /* denotes a Java VM */
  JNIEnv *env;       /* pointer to native method interface */
  JavaVMInitArgs vm_args; /* JDK/JRE 6 VM initialization arguments */
  JavaVMOption* options = new JavaVMOption[1 + java_opts.size()];

  std::string opt_classpath = "-Djava.class.path=" + mydir() + "/PhyDstar.jar";
  options[0].optionString = &(opt_classpath[0]);  
  for (size_t i = 0; i < java_opts.size(); i++) {
    options[i+1].optionString = &(java_opts[i][0]);
  }
  vm_args.version = JNI_VERSION_1_6;
  vm_args.nOptions = 1 + java_opts.size();
  vm_args.options = options;
  vm_args.ignoreUnrecognized = false;
  /* load and initialize a Java VM, return a JNI interface
   * pointer in env */
  JNI_CreateJavaVM(&jvm, (void**)&env, &vm_args);
  delete options;
  /* invoke the Main.test method using the JNI */
  jclass cls = env->FindClass("PhyDstar");
  jmethodID mid = env->GetStaticMethodID(cls, "main", "([Ljava/lang/String;)V");

  jclass jstring = env->FindClass("java/lang/String");
  jobjectArray phydstar_args = env->NewObjectArray(2, jstring, 0);


  env->SetObjectArrayElement(phydstar_args, 0, env->NewStringUTF("-i"));
  env->SetObjectArrayElement(phydstar_args, 1, env->NewStringUTF(tempfilename.c_str()));
  env->CallStaticVoidMethod(cls, mid, phydstar_args);

  if(env->ExceptionOccurred()) {
    // Print exception caused by CallVoidMethod
    env->ExceptionDescribe();
    env->ExceptionClear();
  }
  /* We are done. */
  jvm->DestroyJavaVM();

}

std::string BioNJStar(TaxonSet& ts, DistanceMatrix& dm, std::vector<std::string>& java_opts) {

  std::string fname = tmpnam(0);
  

  std::ofstream of(fname);
  write_matrix(ts, dm, of);
  of.close();
  
  runPhyDStar("BioNJ", fname, java_opts);

  std::string phydstar_tree;

  std::ifstream treein(std::string(fname) + "_bionj.t");
  treein >> phydstar_tree;

  //  remove(phydstar_tree.begin(), phydstar_tree.end(), 't');
  
  std::string unmapped = unmap_newick_names(phydstar_tree, ts);
  
  
  return unmapped;
}
#else //no USE_PHYDSTAR
#include <glog/logging.h>

std::string BioNJStar(TaxonSet& ts, DistanceMatrix& dm, std::vector<std::string>& java_opts) {
  LOG(FATAL) << "PhyD* was not enabled while compiling ASTRID!\n"
             << "Make sure java is set up correctly and try running ASTRID-phydstar\n";
  return "";
}

#endif

